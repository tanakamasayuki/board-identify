# Changelog / 変更履歴

## Unreleased
- (EN) Publish a transport-qualified link, `<board-id>-<uart|usb|probe>`, alongside the board name, so a board reachable through both a USB-UART bridge and its own USB peripheral is addressable path by path
- (JA) ボード名と並んでトランスポート付きのリンク `<board-id>-<uart|usb|probe>` を公開し、USB-UART ブリッジとオンボードのネイティブ USB の両方で到達できるボードを経路ごとに指定できるようにした
- (EN) Hand the shared board name to the port most likely to still be there, and back to the port that still claims it when the holder disappears, instead of leaving the board nameless
- (JA) 共有されるボード名は、より残っていそうなポートが受け取り、保持していたポートが消えたときは、まだそれを名乗っているポートへ戻すようにした。以前はボードが名無しになっていた
- (EN) Keep the state of a live port that holds no link, because it is a claim on the board rather than a receipt for a link
- (JA) リンクを 1 つも保持していない生きたポートの状態を維持するようにした。それはリンクの受領証ではなくボードへの主張だから
- (EN) Name an Espressif native USB port from its serial descriptor, which is the eFuse MAC, instead of running `esptool` and losing the port to the reset that ends the run
- (JA) Espressif のネイティブ USB ポートは、eFuse MAC であるシリアルディスクリプタから命名するようにした。`esptool` を実行すると、その最後のリセットでポート自体を失うため
- (EN) Record `unique ID -> chip name` in `/run/board-identify/variants.json` whenever a target is reached, so the ports that cannot ask do not have to
- (JA) ターゲットへ到達するたびに `固有 ID -> チップ名` を `/run/board-identify/variants.json` に記録し、自分では尋ねられないポートが尋ねずに済むようにした

## 1.0.0
- (EN) Identify Espressif targets through `esptool` and name them by their eFuse MAC
- (JA) Espressif ターゲットを `esptool` で識別し、eFuse MAC で命名
- (EN) Identify WCH-Link debug probes from USB descriptors alone, and the WCH RISC-V target behind one from its chip signature and factory UUID
- (JA) WCH-Link デバッグプローブを USB ディスクリプタだけで識別し、その先の WCH RISC-V ターゲットをチップシグネチャと工場出荷時 UUID で識別
- (EN) Recover a WCH-Link left holding a corrupted readback of its target by making it look again, without resetting the board
- (JA) WCH-Link がターゲットの壊れた読み取り値を抱えた状態から、ボードをリセットせず見直させて復旧
- (EN) Recognise 825 USB VID/PID pairs from a table merged from `arduino-cli board details`, naming a board from its descriptors with no USB traffic and no reset
- (JA) `arduino-cli board details` からマージした 825 組の USB VID/PID 表を同梱し、USB 通信もリセットもなしにディスクリプタからボードを命名
- (EN) Skip `esptool` on a port whose VID/PID belongs to another family, so an Arduino UNO or a Raspberry Pi Pico is no longer reset on every plug event
- (JA) VID/PID が他ファミリのポートでは `esptool` を実行せず、Arduino UNO や Raspberry Pi Pico が挿すたびリセットされないようにした
- (EN) Never let a stock USB-UART bridge ID (CH340, CP2102, FT232, PL2303) name a board or rule a probe out, in either direction
- (JA) 汎用 USB-UART ブリッジの ID（CH340、CP2102、FT232、PL2303）に、ボードの命名もプローブの除外もさせない
- (EN) Publish one `/run/board-identify/by-id/` link per identity of a port, so a debug probe and the board on its pins each get a name
- (JA) ポートが持つ同一性ごとに `/run/board-identify/by-id/` のリンクを公開し、デバッグプローブとその先のボードがそれぞれ名前を持つ
- (EN) Drop only the names a port stops claiming, and remove links and state when a device disappears
- (JA) 公開しなくなった名前だけを削除し、デバイスが外れたらリンクと状態を取り除く
- (EN) Add the `identify`, `remove` and `cleanup` subcommands, with `--json`, `--no-publish`, `--no-target-probe` and `--runtime-dir`
- (JA) `identify`・`remove`・`cleanup` サブコマンドと、`--json`・`--no-publish`・`--no-target-probe`・`--runtime-dir` を追加
- (EN) Record the release that wrote each state file under `/run/board-identify/state/`
- (JA) `/run/board-identify/state/` の各状態ファイルに、それを書いたリリースを記録
- (EN) Install udev rules and systemd units so a port is identified as it appears
- (JA) udev ルールと systemd ユニットを同梱し、ポートが現れた時点で識別
- (EN) Cut releases from a `Release` workflow that runs the checks, closes this changelog, tags `v<version>` and publishes the wheel and sdist
- (JA) チェック実行・本ファイルの節を閉じる・`v<version>` のタグ付け・wheel と sdist の公開を行う `Release` ワークフローでリリースを作成
- (EN) Publish English and Japanese documentation side by side
- (JA) 英語と日本語のドキュメントを併記
