# board-identify

*[English](README.md) | [日本語](README.ja.md)*

シリアルデバイスとして接続されたマイコンボードを識別し、ハードウェア固有の識別子にもとづく安定したシンボリックリンクを公開します。

## 当面の対象

`esptool` を用いて Espressif デバイスを識別し、WCH-Link デバッグプローブについてはプローブ自身とデバッグ端子の先にあるボードの両方を識別して、次のようなリンクを作成します。

```text
/run/board-identify/by-id/esp32-s3-7cdfa1123456         -> /dev/ttyUSB2
/run/board-identify/by-id/ch32x035c8t6-1ff9abcd880ebc48 -> /dev/ttyACM4
/run/board-identify/by-id/wch-link-fc928f068181         -> /dev/ttyACM4
```

USB トランスポートとターゲットボードは別物として扱います。CH340、FTDI、CP210x のシリアル番号が示すのは変換アダプタであり、その先にあるボードとは限りません。デバッグプローブはその両方を兼ねるので、ターゲット用のリンクと並んで自分のリンクも持ちます。

## まず標準の仕組みを検討してください

本ツールは、Linux 標準の仕組みでは対応できない場合のためのものです。**次のいずれかで用が足りるなら、そちらを使ってください。** 安定していて、ボードに触れず、何もインストールする必要がありません。

```bash
# USB の VID/PID と iSerial ディスクリプタから作られるデバイスごとのリンク。
ls -l /dev/serial/by-id/

# 物理的な USB ポートの経路から作られるリンク。
ls -l /dev/serial/by-path/

# udev が把握している情報。
udevadm info -q property -n /dev/ttyUSB0 | grep -E 'ID_VENDOR_ID|ID_MODEL_ID|ID_SERIAL_SHORT|ID_PATH'
```

ディスクリプタでアダプタを固定する udev ルールの例:

```udev
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{serial}=="0001B2C3", SYMLINK+="esp32-lab1"
```

固有のシリアル番号を持つアダプタ（多くの FTDI、多くの CP210x、ESP32-S3/C3 の USB-Serial/JTAG や RP2040、多くの Arduino ボードのようなネイティブ USB 機器）や、`by-path` による物理ポート固定は、これで十分にカバーできます。

`board-identify` を持ち出すのは、どちらも使えない場合だけです。たとえばシリアル番号を一切報告しない CH340、同一のアダプタが複数ある構成、そして次に述べる WSL + USB/IP の環境です。

デバッグプローブはそれ自体が別のケースです。`by-id` が名前を付けるのはプローブであって、指したいものとは違うことがよくあります。WCH-LinkE の UART は既に `/dev/serial/by-id/usb-wch.cn_WCH-Link_FC928F068181-if01` として現れますが、この名前が追従するのはプローブであってボードではありません。デバッグ端子の先のボードを差し替えても名前は変わりません。ボードに追従する名前が欲しい場合が、後述の WCH-Link プローブの出番です。

## 想定環境: WSL 上の Linux（USB/IP 経由）

主な対象は、[usbipd-win](https://github.com/dorssel/usbipd-win) でデバイスを転送した WSL 上の Linux です。ここでは標準の仕組みが破綻します。

- Windows 側のバス ID（`usbipd list` に出る `1-4` など）は Linux 側には存在しないため、udev ルールで照合できません。
- 転送されたデバイスは仮想ホストコントローラ上に現れるので、`ID_PATH` や `/dev/serial/by-path/` は `platform-vhci_hcd.0-usb-0:1:1.0` のようになります。このポート番号は物理的な接続位置ではなく attach した順序で決まるため、順序が変われば変化します。
- アダプタがシリアル番号を報告する場合は `/dev/serial/by-id/` が有効で、使えるならそちらが第一選択です。

そのため `board-identify` は、どの順序で attach し直しても変わらない識別子を、ターゲットボード自身に問い合わせます。

### オートアタッチとのトレードオフ

`usbipd attach --auto-attach` は便利です。デバイスが現れた時点で転送し、切断後も再接続してくれます。しかし attach される順序はデバイスが現れた順であり、順不同です。シリアル番号を報告しないアダプタ（多くの CH340 モジュールなど）では、どの `/dev/ttyUSB*` がどのボードなのかを判別できなくなります。次のどちらかを選ぶ必要があります。

- **毎回同じ順序で手動 attach する。** ポート番号は予測可能になりますが、セッションごとに決まった手順を踏む手間がかかります。
- **オートアタッチと本ツールのような仕組みを併用する。** ボード自身を識別するため、順序を気にする必要がなくなります。

また USB/IP では attach がときどき外れます。サスペンド、Windows 側の Wi-Fi や VPN の切り替え、USB の一時的な不調などで十分に起こります。オートアタッチにしていない場合、外れたことに気づいて attach コマンドを手で叩き直す必要があり、復帰が面倒です。オートアタッチを有効にしたうえで、順序の問題はこちらで解決する — というのが本ツールの主な動機です。

## デバッグプローブ

WCH-Link は 2 段階で識別し、それぞれが自分のリンクを作ります。

```bash
sudo .venv/bin/board-identify identify /dev/ttyACM4
# /run/board-identify/by-id/ch32x035c8t6-1ff9abcd880ebc48 -> /dev/ttyACM4
# /run/board-identify/by-id/wch-link-fc928f068181         -> /dev/ttyACM4
```

- **プローブ自身**を sysfs の USB ディスクリプタから。USB 通信は発生せず、tty も開かないので、何も乱しません。
- **デバッグ端子の先のボード**をチップのシグネチャと工場出荷時に書き込まれた UUID から。これはプローブのベンダインタフェース上での短いやり取りが必要で、その間ターゲットのコアを保持し、終われば解放します。

ターゲットに触るのは 2 段目だけで、`--no-target-probe` で無効にできます。

```bash
sudo .venv/bin/board-identify identify --no-target-probe /dev/ttyACM4
# /run/board-identify/by-id/wch-link-fc928f068181 -> /dev/ttyACM4
```

ターゲットのリンク名は、チップを特定できる範囲でできるだけ細かくなります。型番のわかるシグネチャなら `ch32x035` ではなく `ch32x035c8t6` です。チップのシグネチャは [probe-rs](https://github.com/probe-rs/probe-rs) と [ch32fun](https://github.com/cnlohr/ch32fun) から転記しています。どちらにも載っていないシグネチャはシリーズ名、さらに生の 16 進へフォールバックします。

2 段目が必要とするのは RISC-V モード（`1a86:8010`、`1a86:8012`）です。ARM モード（`1a86:8011`）ではプローブは CMSIS-DAP を話すので、プローブ自身の名前だけを付けます。

## 必要なもの

セットアップの前に [uv](https://docs.astral.sh/uv/) をインストールしてください。

## 開発環境の準備

```bash
uv sync
```

チェックの実行:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
```

## 手動での利用

```bash
sudo .venv/bin/board-identify identify /dev/ttyUSB0
```

機械可読な出力:

```bash
sudo .venv/bin/board-identify identify --json /dev/ttyUSB0
```

公開せずに識別だけを行う、あるいは `/run` 以外へ公開する:

```bash
sudo .venv/bin/board-identify identify --no-publish /dev/ttyUSB0
sudo .venv/bin/board-identify --runtime-dir /tmp/board-identify identify /dev/ttyUSB0
```

特定ポートのリンクと状態を削除する、または不整合になったものを一括で掃除する:

```bash
sudo .venv/bin/board-identify remove ttyUSB0
sudo .venv/bin/board-identify cleanup
```

デバッグプローブの先のボードと通信する段階を省く:

```bash
sudo .venv/bin/board-identify identify --no-target-probe /dev/ttyACM4
```

終了コード: `0` 成功、`1` エラー、`2` ボードを識別できなかった。

## OS への組み込み

インストーラは `/opt/board-identify` 配下に uv 管理の環境を作成し、同梱の udev ルールと systemd ユニットを配置します。

```bash
sudo UV_BIN="$(command -v uv)" ./scripts/install.sh
```

systemd サービスが実行するのは次のコマンドです。

```text
/opt/board-identify/.venv/bin/board-identify
```

アンインストール:

```bash
sudo ./scripts/uninstall.sh
```

詳細とトラブルシューティングは [`docs/operations.ja.md`](docs/operations.ja.md) を参照してください。

## 識別の方針

1. シリアルデバイスと USB のメタデータを調べる。
2. 必要に応じてターゲット固有のプローブを実行する。
3. そのポートが持つ同一性ごとに `<variant>-<unique-id>` を生成する。
4. `/run/board-identify/by-id/` 配下にそれぞれのシンボリックリンクをアトミックに公開する。
5. 現在の状態を `/run/board-identify/state/` に保存する。

## 適用範囲: 開発環境専用

USB の VID/PID で特定できないものは、ターゲットと通信して識別します。そしてこのプローブは**ボードをリセットします**。`esptool` が DTR/RTS を操作してブートローダへ入るため、ポートが現れるたびに動作中のファームウェアが再起動されます。

導入前に受け入れる必要がある影響:

- プローブは `ttyUSB*` と `ttyACM*` のすべてのポートで実行されるため、対象外のボードも含め、接続したボードが再起動します。
- 測定中・ロギング中・ハードウェアを駆動中のデバイスは中断されます。
- プローブ実行中のシリアル出力は失われます。

開発マシンで使ってください。**安定した環境が必要な用途 — 本番環境、無人のテスト装置、再起動が許されないハードウェアの制御 — には利用しないでください。** そうした環境では、上に示した `/dev/serial/by-id/` や udev ルールでデバイスを固定してください。

現状: VID/PID による非侵襲パスは未実装のため、ディスクリプタだけで識別できるデバイスも含め、**対象となるすべてのポートが現時点ではプローブされます。** [プローブの実装予定](#プローブの実装予定) を参照してください。

## プローブの実装予定

- [x] eFuse MAC による Espressif ESP32 ファミリ
- [x] WCH-Link デバッグプローブと、その先の WCH RISC-V ターゲット（部品 UUID による）
- [ ] ネイティブ USB シリアルディスクリプタ
- [ ] Arduino ボード
- [ ] RP2040
- [ ] STM32
- [ ] 汎用のファームウェア識別プロトコル

[`docs/adding-a-probe.ja.md`](docs/adding-a-probe.ja.md) を参照してください。

## ドキュメント

- [アーキテクチャ](docs/architecture.ja.md)
- [識別子の形式](docs/identifier-format.ja.md)
- [運用](docs/operations.ja.md)
- [プローブの追加](docs/adding-a-probe.ja.md)
- [変更履歴](CHANGELOG.ja.md)
