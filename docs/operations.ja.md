# 運用

*[English](operations.md) | [日本語](operations.ja.md)*

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

ユニットの `TimeoutStartSec=60` は、`board_identify.probes.espressif` のプローブタイムアウト（既定 30 秒）より大きい値を保ってください。小さいと、応答が遅いプローブが結果を返す前に強制終了されます。

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

終了コード 2 で識別に失敗する場合、どのプローブも認識できる応答が得られなかったことを意味します。よくある原因は、ボード上のアプリケーションがポートを占有している、ブートローダへの手動遷移が必要、シリアルモニタや ModemManager などの別プロセスが先にポートを開いた、などです。最後の例は `ENV{ID_MM_DEVICE_IGNORE}="1"` のような udev ルールで ModemManager の対象から外すと回避できます。

プローブはターゲットをリセットします。接続中もボードを止めずに動かし続けたい環境には導入しないでください。

[アーキテクチャ](architecture.ja.md) も参照してください。
