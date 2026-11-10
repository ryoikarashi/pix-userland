# Apple TV 向け地上波 IPTV

`pixd` → `pix-ts` → mirakc → Apple TV の IPTV プレイヤーという構成です。
mirakc が選局、サービス分離、番組表収集、M3U / XMLTV 配信を担当します。
配布イメージは版と digest を固定しています。

## この設定の前提

- Raspberry Pi ARM64 / Debian 13、実行ユーザー `pi`（UID/GID 1000）。
- 修正済み `pixd.service` が `/run/pix-userland`、instance `tuner` で稼働。
- `/home/pi/pix-userland/build/cmake/pix-ts` が存在する。
- LAN アドレスは `192.168.1.16`。`config.yml` の待受アドレスを実機に合わせる。
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

## 検証・運用

```sh
systemctl is-active pixd pix-iptv
sudo journalctl -u pix-iptv -n 80 --no-pager
python3 packaging/iptv/check.py http://192.168.1.16:40772
```

検証スクリプトは全チャンネルへ順番に選局するので、視聴していない時間に実行してください。
M3U と XMLTV の ID 対応、番組情報の存在、各 URL の TS パケットを検査します。

2026-11-10、Raspberry Pi 3 Model B / Debian 13 / PIX-DT295 で7局すべてを検証しました。
XMLTV は2,203番組（11月18日未明まで）を収録し、全局で MPEG-2 映像
（1440×1080）と AAC 音声（48 kHz）を確認しました。`pixd` の通常再起動後も
配信が自動復帰し、番組表キャッシュを復元して同じ7局の検査に合格しています。
Apple TV アプリ内での番組表表示・リモコン操作は、この検証には含みません。

DT295 は1系統です。異なる物理チャンネルを同時に視聴できません。
mirakc の番組表収集は視聴より低優先度で、視聴要求があれば中断されます。
定期収集は毎日 04:30 / 16:30、局情報再取得は 04:00、時計同期は 04:15 です。
初回の番組表収集には数分以上かかります。全局の情報がそろわない場合は、
視聴を停止して次の収集を待ってください。

LAN 内向けの配信です。ルーターでポートをインターネットへ公開しないでください。
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
