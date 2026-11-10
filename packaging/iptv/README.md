# Apple TV 向け地上波 IPTV

`pixd` → `pix-ts` → mirakc → Apple TV の IPTV プレイヤーという構成です。
mirakc が選局、サービス分離、番組表収集、M3U / XMLTV 配信を担当します。
配布イメージは版と digest を固定しています。

## この設定の前提

- Raspberry Pi ARM64 / Debian 13、実行ユーザー `pi`（UID/GID 1000）。
- 修正済み `pixd.service` が `/run/pix-userland`、instance `tuner` で稼働。
- `/home/pi/pix-userland/build/cmake/pix-ts` が存在する。
- LAN アドレスは `192.168.1.16`。`config.yml` の待受アドレスを実機に合わせる。
- Tailscale アドレスは `100.101.158.9`。Pi の Tailscale が接続済みであること。
- アンテナと B-CAS カードは接続済み。DT295 内部で復号するため、外部 B25 は使わない。

`config.yml` のチャンネルは地域・受信設備に依存します。物理チャンネル番号と
リモコン番号は異なります。京都の実機で取得したサービス ID を使い、各局の
主チャンネルだけを公開します。別地域では物理チャンネルとサービス ID を変更してください。
録画・タイムシフトは有効にしていません。

| 局 | 物理チャンネル | サービス ID |
| --- | ---: | ---: |
| NHK総合・京都 | 25 | 41984 |
| NHK Eテレ | 40 | 2056 |
| MBS | 33 | 2064 |
| KBS京都 | 23 | 42032 |
| ABC | 38 | 2072 |
| 関西テレビ | 42 | 2080 |
| 読売テレビ | 35 | 2088 |

## 導入

Pi 上で実行します。`pix-live` はチューナーを常時占有するため停止します。

```sh
sudo apt-get install docker.io docker-cli docker-compose
sudo install -d /opt/pix-iptv /var/lib/pix-iptv/epg
sudo chown 1000:1000 /var/lib/pix-iptv/epg
sudo install -m 0644 packaging/iptv/compose.yml packaging/iptv/config.yml /opt/pix-iptv/
sudo install -m 0644 packaging/iptv/pix-iptv.service /etc/systemd/system/
sudo install -d /etc/systemd/system/pixd.service.d
sudo install -m 0644 packaging/iptv/pixd-iptv.conf /etc/systemd/system/pixd.service.d/iptv.conf
sudo docker-compose -f /opt/pix-iptv/compose.yml config --quiet
sudo docker-compose -f /opt/pix-iptv/compose.yml pull
sudo systemctl disable --now pix-live
sudo systemctl daemon-reload
sudo systemctl enable --now pix-iptv
```

USB デバイスはホストの `pixd` だけが保持します。コンテナは UID 1000 で動作し、
`pix-ts` と IPC ディレクトリを読み取り専用で参照します。
番組表キャッシュは `/var/lib/pix-iptv/epg` に保持します。
再起動時は12時間以内に取得したキャッシュを再利用します。
`pixd` の再起動に合わせてコンテナも再起動し、IPC ディレクトリをマウントし直します。

## Apple TV への登録

IPTVX など、M3U と XMLTV を指定できるアプリで新しいプレイリストを追加します。

- M3U URL: `http://192.168.1.16:40772/api/iptv/playlist`
- EPG / XMLTV URL: `http://192.168.1.16:40772/api/iptv/xmltv`

名前は「自宅 地上波」など任意です。Apple TV と Pi を同じ LAN に接続し、
プレイリストと番組表の読み込み後にチャンネルを選択します。
アプリ側の映像形式は MPEG-TS の直接再生を使います。サーバーでの再エンコードは行いません。

Pi 上で Tailscale Serve の TCP 転送を有効にします。`--bg` の設定は再起動後も保持されます。

```sh
sudo tailscale serve --bg --tcp=40772 tcp://127.0.0.1:40772
sudo tailscale serve status
```

mirakc 3.4.92 は Tailscale の IPv4 アドレスからの直接アクセスを拒否するため、
Serve で localhost へ中継します。mirakc の待受に Tailscale IP を追加する必要はありません。
この転送は Tailscale 内だけで利用できます。

外出先では視聴端末も Pi と同じ Tailscale ネットワークへ接続し、次の URL を登録します。
M3U を Tailscale の URL から読み込むことで、一覧内の再生 URL も同じアドレスになります。

- M3U URL: `http://100.101.158.9:40772/api/iptv/playlist`
- EPG / XMLTV URL: `http://100.101.158.9:40772/api/iptv/xmltv`

外出先では、自宅の上りと視聴先の下りに放送 TS を送れる帯域が必要です。
転送を止める場合は `sudo tailscale serve --tcp=40772 off` を実行します。

## 検証・運用

```sh
systemctl is-active pixd pix-iptv
sudo journalctl -u pix-iptv -n 80 --no-pager
python3 packaging/iptv/check.py http://192.168.1.16:40772
```

検証スクリプトは全チャンネルへ順番に選局するので、視聴していない時間に実行してください。
M3U と XMLTV の ID 対応、番組情報の存在、各 URL の TS パケットを検査します。
Tailscale 経由を検証する場合は、同じネットワークに参加した別端末から
`python3 packaging/iptv/check.py http://100.101.158.9:40772` を実行します。

2026-11-10、Raspberry Pi 3 Model B / Debian 13 / PIX-DT295 で7局すべてを検証しました。
XMLTV は2,203番組（11月18日未明まで）を収録し、全局で MPEG-2 映像
（1440×1080）と AAC 音声（48 kHz）を確認しました。`pixd` の通常再起動後も
配信が自動復帰し、番組表キャッシュを復元して同じ7局の検査に合格しています。
別の端末から Tailscale Serve 経由でも7局・2,203番組の同じ検査に合格しています。
Apple TV アプリ内での番組表表示・リモコン操作は、この検証には含みません。

選局待ち時間の短縮には [PR #94](https://github.com/Khronos31/pix-userland/pull/94)
を適用しています。USB 転送を64 KiB×8本から8 KiB×64本に変更し、
同時転送量512 KiBとリング容量32 MiBを維持したまま、初期の番組情報を早く取得します。
既存の EP81 再取得修正も保持しています。

同日、同じ Pi と Tailscale 経由の NHK総合 URL で、HTTP要求から最初の188バイトの
TSパケットを読み終えるまでを3回ずつ測定しました。

| | 1回目 | 2回目 | 3回目 | 平均 |
| --- | ---: | ---: | ---: | ---: |
| 適用前 | 10.789秒 | 10.836秒 | 10.700秒 | 10.775秒 |
| 適用後 | 3.073秒 | 2.793秒 | 2.600秒 | 2.822秒 |

これは最初の TS までの時間で、UHF のバッファや映像表示までの時間は含みません。

DT295 は1系統です。異なる物理チャンネルを同時に視聴できません。
mirakc の番組表収集は視聴より低優先度で、視聴要求があれば中断されます。
定期収集は毎日 04:30 / 16:30、局情報再取得は 04:00、時計同期は 04:15 です。
初回の番組表収集には数分以上かかります。全局の情報がそろわない場合は、
視聴を停止して次の収集を待ってください。

LAN と Tailscale 内向けの配信です。ルーターでポートをインターネットへ公開しないでください。
Pi の IP が変わる場合は DHCP 予約を設定するか、待受設定とアプリの URL を変更します。

## 以前の固定チャンネル配信へ戻す

```sh
sudo systemctl disable --now pix-iptv
sudo rm /etc/systemd/system/pixd.service.d/iptv.conf
sudo systemctl daemon-reload
sudo systemctl enable --now pix-live
```

## 参照

- [mirakc 設定（3.4.92）](https://github.com/mirakc/mirakc/blob/3.4.92/docs/config.md)
- [mirakc IPTV API](https://github.com/mirakc/mirakc/blob/3.4.92/docs/web-api.md)
- [mirakc 3.4.92 のアクセス制御](https://github.com/mirakc/mirakc/blob/3.4.92/mirakc-core/src/web/access_control.rs)
- [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve)
