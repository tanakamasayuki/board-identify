# 運用

*[English](operations.md) | [日本語](operations.ja.md)*

## インストール前に

プローブはターゲットを乱します。`esptool` は接続イベントのたびにファームウェアを再起動させ、WCH-Link の attach はターゲットのコアを halt して解放します。導入は開発マシンに限定し、使える場面では `/dev/serial/by-id/` や USB ディスクリプタを照合する udev ルールを優先してください。README の [まず標準の仕組みを検討してください](../README.ja.md#まず標準の仕組みを検討してください) を参照。

## WSL と USB/IP

主対象の環境では、[usbipd-win](https://github.com/dorssel/usbipd-win) で Windows からデバイスを転送します。

```powershell
usbipd list                        # BUSID（例: 1-4）を確認する
usbipd bind --busid 1-4            # 管理者権限で一度だけ
usbipd attach --wsl --busid 1-4
usbipd attach --wsl --busid 1-4 --auto-attach   # 再接続し続ける。停止するまで常駐
```

### オートアタッチか、固定順の手動 attach か

オートアタッチはデバイスが現れ次第すぐ転送し、切断後も復帰させてくれますが、順序はデバイスが到着した順になります。シリアル番号を持たないアダプタ（多くの CH340 モジュールなど）では、結果として得られる `/dev/ttyUSB*` の番号がどのボードのものか特定できません。現実的な構成は次の 2 つです。

| 構成 | ポート番号 | 代償 |
| --- | --- | --- |
| 毎回同じ順序で手動 attach | 予測可能 | セッションごとの決まった手順。attach が外れたら気づいて手で復旧する必要がある |
| オートアタッチ + `board-identify` | 不定だが問題にならない | attach のたびにプローブがボードを乱す |

attach は時折外れます。サスペンド、Windows 側の Wi-Fi や VPN の切り替え、USB の一時的な不調などが原因です。オートアタッチなら手を介さずに復帰するため、通常はこれを有効にしたまま、順序の問題は Linux 側で解決します。

WSL 側では `/dev/ttyUSB0` や `/dev/ttyACM0` として現れます。

```bash
# Windows 側の BUSID はここには現れず、パスは attach 順に従う。
udevadm info -q property -n /dev/ttyUSB0 | grep -E 'ID_PATH|ID_SERIAL'
# ID_PATH=platform-vhci_hcd.0-usb-0:1:1.0
```

この環境での注意点:

- Windows 側での detach や `wsl --shutdown` は、物理的に抜いたときと同じ `remove` イベントになるため、リンクと状態は通常どおり掃除されます。
- attach する順序が変わると `ID_PATH` が変わり、`/dev/serial/by-path/` も変わります。これが本ツールの存在理由です。
- ルールを動作させるにはディストリビューション内で udev が動いている必要があります。`systemctl status systemd-udevd` で確認し、古い WSL 構成では `/etc/wsl.conf` の `[boot]` / `systemd=true` で systemd を有効にして `wsl --shutdown` で再起動してください。
- リンクは `/run` 配下にあるため、WSL を起動するたびに作り直されます。

## インストール

```bash
sudo UV_BIN="$(command -v uv)" ./scripts/install.sh
```

インストーラはソースツリー（`.git`、開発用 `.venv`、各種キャッシュを除く）を `/opt/board-identify` へコピーし、`uv sync --no-dev --frozen` を実行して、次のファイルを配置します。

| ファイル | 配置先 |
| --- | --- |
| `udev/90-board-identify.rules` | `/etc/udev/rules.d/` |
| `systemd/board-identify@.service` | `/etc/systemd/system/` |
| `systemd/board-identify-cleanup.service` | `/etc/systemd/system/` |

別の場所に入れる場合は `BOARD_IDENTIFY_INSTALL_ROOT` を指定します。アンインストールは `sudo ./scripts/uninstall.sh` で、`/run/board-identify` も削除されます。

## 接続時と切断時の動作

- 接続: udev が `SYSTEMD_WANTS` を設定し、systemd が `board-identify@ttyUSB0.service` を起動して `board-identify identify /dev/ttyUSB0` を実行します。
- 切断: `BindsTo=dev-ttyUSB0.device` によりユニットが停止し、その `ExecStop=` が `board-identify remove ttyUSB0` を実行します。加えて udev の `remove` ルールが `board-identify-cleanup.service` を起動します。

ユニットの `TimeoutStartSec=60` は、`board_identify.probes.espressif` のプローブタイムアウト（既定 30 秒）より大きい値を保ってください。小さいと、応答が遅いプローブが結果を返す前に強制終了されます。WCH-Link はディスクリプタから認識され 1 秒を大きく下回って応答するので、この上限に近づくことはありません。

## デバッグプローブの USB 権限

デバッグプローブの先のボードを識別するには、tty だけでなくプローブのベンダ USB インタフェースへのアクセスが必要です。systemd ユニットは root で動くため、インストール済みの構成では追加設定は要りません。一般ユーザーで手動実行する場合は必要で、権限がないとプローブ自身には名前が付きますが、その先のターゲットには付きません。

```bash
# 到達できているかの確認。wch-link のエントリだけが返るなら、
# ベンダインタフェースを開けていない。
board-identify identify --json --no-publish /dev/ttyACM4

# RISC-V モードの WCH-Link へのアクセスを許可するルール。
sudo tee /etc/udev/rules.d/99-wch-link.rules <<'RULE'
SUBSYSTEM=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="8010", GROUP="plugdev", MODE="0660"
SUBSYSTEM=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="8012", GROUP="plugdev", MODE="0660"
RULE
sudo udevadm control --reload
```

## トラブルシューティング

```bash
# 現在接続されているものすべてを再識別する。
sudo udevadm trigger --subsystem-match=tty

# 特定ポートのログを追う。
journalctl -u board-identify@ttyUSB0.service -f

# /run を変更せずに判定結果だけを確認する。
sudo /opt/board-identify/.venv/bin/board-identify identify --json --no-publish /dev/ttyUSB0

# 古くなったリンクと状態を手動で掃除する。
sudo /opt/board-identify/.venv/bin/board-identify cleanup
```

ベンダインタフェースを既に別のセッション（`gdb`、`minichlink`、`wlink`、OpenOCD など）が掴んでいるデバッグプローブには、ターゲットについて尋ねられません。これはエラーではありません。プローブ自身はディスクリプタから公開され、ターゲットのリンクはそのセッションが終わったあとの次の接続イベントか手動再実行で復活します。意図的にプローブだけを公開したい場合、あるいは動作中のターゲットに一切触れたくない場合は次のようにします。

```bash
sudo /opt/board-identify/.venv/bin/board-identify identify --no-target-probe /dev/ttyACM4
```

終了コード 2 で識別に失敗する場合、どのプローブも認識できる応答が得られなかったことを意味します。よくある原因は、ボード上のアプリケーションがポートを占有している、ブートローダへの手動遷移が必要、シリアルモニタや ModemManager などの別プロセスが先にポートを開いた、などです。最後の例は `ENV{ID_MM_DEVICE_IGNORE}="1"` のような udev ルールで ModemManager の対象から外すと回避できます。

プローブはターゲットを乱します。接続中もボードを止めずに動かし続けたい環境には導入しないでください。

[アーキテクチャ](architecture.ja.md) も参照してください。
