# プローブの追加

*[English](adding-a-probe.md) | [日本語](adding-a-probe.ja.md)*

1. `src/board_identify/probes/` にクラスを追加する。
2. `probes/base.py` の `Probe` プロトコルに合わせて `supports(port)` と `identify(port)` を実装する。
3. そのポートが持つ同一性ごとに `Identification` を、具体的なものから順に返す。確実に識別できたものが何もなければ空のリストを返す。
4. `identify.py` の `default_probes()` にプローブを登録する。
5. フィクスチャを用いた単体テストを追加する。

トランスポートの USB シリアル番号は、原則としてターゲットの固有 ID ではなくメタデータとして記録します。例外はデバッグプローブです。それ自体が 1 つのデバイスなので、ターゲットの分とは別に自分の `Identification` を持ちます。

## 満たすべき約束

- `supports()` は安価であること。ポートを開いてはいけません。あくまで事前フィルタであり、確定的な一致判定ではありません。`usbinfo` 経由の sysfs 読み取りは十分に安価ですが、tty のオープンや USB 通信はそうではありません。
- `identify()` は認識できないものに対して空のリストを返します。タイムアウト、外部ツールの非ゼロ終了、解析できない出力もすべて含みます。応答しないデバイスに対して例外を送出してはいけません。
- `identify()` は稼働中のデバイス上で実行されます。直前に別のプローブがリセットを行った可能性を前提にしてください。`default_probes()` では侵襲性の低いものから順に並べます。
- 返す `Identification` はすべて、渡されたポートを指していなければなりません。混在した集合は `publish()` が拒否します。
- ターゲットを乱す処理は `probe_target` の後ろに置きます。`default_probes()` がこれを渡し、`--no-target-probe` が無効化します。無効のときはディスクリプタを読む以上のことをしてはいけません。
- `normalize_component()` と `normalize_unique_id()` で正規化し、その `ValueError` は「識別できなかった」として扱います。

## テストしやすい構造

ハードウェアなしでテストできるよう、解析処理と入出力を分離します。`EspressifProbe` は、サブプロセスを実行する `identify()` と、取得済み出力に対する純粋関数である `parse()` / `extract_*()` に分かれています。`WchLinkProbe` は 3 つに分かれます。デバイスを開く `query()`、`read` / `write` を持つ任意のオブジェクトに対してコマンド列を流す `session()`、応答 1 件を解析する `parse_*()` です。

実際のデバイス出力は `tests/fixtures/<tool>/` に記録し、`tests/conftest.py` の `esptool_output` または `wch_reply` フィクスチャと同じ要領で読み込みます。成功例に加えて、応答しなかったデバイスなどの失敗例も最低 1 つ含めてください。sysfs を読むプローブは `sysfs` フィクスチャでテストできます。これは実際の USB シリアルポートと同じ形のツリーを組み立てます。

[アーキテクチャ](architecture.ja.md) と [識別子の形式](identifier-format.ja.md) も参照してください。
