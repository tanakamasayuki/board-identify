# プローブの追加

*[English](adding-a-probe.md) | [日本語](adding-a-probe.ja.md)*

1. `src/board_identify/probes/` にクラスを追加する。
2. `probes/base.py` の `Probe` プロトコルに合わせて `supports(port)` と `identify(port)` を実装する。
3. ターゲットを確実に識別できたときだけ `Identification` を返す。
4. `identify.py` の `default_probes()` にプローブを登録する。
5. フィクスチャを用いた単体テストを追加する。

トランスポートの USB シリアル番号は、原則としてターゲットの固有 ID ではなくメタデータとして記録します。

## 満たすべき約束

- `supports()` は安価であること。ポートを開いてはいけません。あくまで事前フィルタであり、確定的な一致判定ではありません。
- `identify()` は認識できないものに対して `None` を返します。タイムアウト、外部ツールの非ゼロ終了、解析できない出力もすべて含みます。応答しないデバイスに対して例外を送出してはいけません。
- `identify()` は稼働中のデバイス上で実行されます。直前に別のプローブがリセットを行った可能性を前提にしてください。`default_probes()` では侵襲性の低いものから順に並べます。
- `normalize_component()` と `normalize_unique_id()` で正規化し、その `ValueError` は「識別できなかった」として扱います。

## テストしやすい構造

ハードウェアなしでテストできるよう、解析処理と入出力を分離します。`EspressifProbe` は、サブプロセスを実行する `identify()` と、取得済み出力に対する純粋関数である `parse()` / `extract_*()` に分かれています。

実際のツール出力は `tests/fixtures/<tool>/` に記録し、`tests/conftest.py` の `esptool_output` フィクスチャと同じ要領で読み込みます。成功例に加えて、応答しなかったデバイスなどの失敗例も最低 1 つ含めてください。

[アーキテクチャ](architecture.ja.md) と [識別子の形式](identifier-format.ja.md) も参照してください。
