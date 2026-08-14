# 識別子の形式

*[English](identifier-format.md) | [日本語](identifier-format.ja.md)*

安定した名前は次の形式です。

```text
<variant>-<unique-id>
```

規則:

- 小文字の ASCII
- 構成要素は `-` で区切る
- 固有 ID から記号類を取り除く
- 固有 ID は可能な限りターゲット自身に由来するものを使う
- 6 文字未満の固有 ID は受け付けない
- 識別子はファイル名として使うため、`/` と NUL は決して含まれない

例:

```text
esp32-s3-7cdfa1123456
rp2040-e6616407e3398c2f
arduino-uno-r4-85735313331351f0
```

## 正規化

`normalize_component()` は NFKC 正規化と小文字化を行い、英数字以外の連続を 1 つの `-` に置き換えます。`normalize_unique_id()` は英数字以外をすべて取り除いて小文字化します。いずれも使える文字が残らなければ `ValueError` を送出し、妥当な構成要素を作れなかったプローブは疑わしい名前を公開せずに `None` を返します。

| 入力 | 出力 |
| --- | --- |
| `ESP32-S3` | `esp32-s3` |
| `ESP32-C3 (QFN32)` | `esp32-c3-qfn32` |
| `7C:DF:A1:12:34:56` | `7cdfa1123456` |

[アーキテクチャ](architecture.ja.md) も参照してください。
