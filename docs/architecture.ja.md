# アーキテクチャ

*[English](architecture.md) | [日本語](architecture.ja.md)*

`board-identify` は 3 つの同一性を区別します。

- **ポート**: `/dev/ttyUSB2` のような、一時的なカーネルノード。
- **トランスポート**: CH340 や FTDI のような USB インタフェースまたは USB-UART ブリッジ。
- **ターゲット**: トランスポートの先にあるマイコンボード。

ターゲットプローブが安定したボード識別子を生成します。パブリッシャはそれを使って `/run/board-identify/by-id/` にシンボリックリンクをアトミックに作成し、一時的なポート名をキーにして状態を保存します。

## モジュール

| モジュール | 責務 |
| --- | --- |
| `paths` | ランタイムの配置。`by-id/` のリンクと `state/` のファイル。 |
| `model` | プローブ 1 回の結果である `Identification`。 |
| `normalize` | チップ名や固有 ID を安全な構成要素へ正規化する。 |
| `probes/` | ターゲットファミリごとのクラス。`identify_port()` が選択する。 |
| `identify` | プローブの振り分け、`publish()`、`remove_port()`。 |
| `cleanup` | 切断されたデバイスが残したリンクと状態の掃除。 |
| `cli` | `identify`、`remove`、`cleanup` の各サブコマンド。 |

## ランタイムの配置

```text
/run/board-identify/
├── by-id/
│   └── esp32-s3-7cdfa1123456 -> /dev/ttyUSB2
└── state/
    └── ttyUSB2.json
```

リンクはボードを、状態ファイルはポートをキーとします。どちらも一時的な名前で書き出してから `os.replace()` で所定の位置へ移動するため、読み手が中途半端なリンクや書きかけの状態ファイルを見ることはありません。

## ライフサイクル

1. udev が新しい `ttyUSB*` / `ttyACM*` ノードを検出し、`board-identify@<port>.service` を起動する。
2. `identify_port()` が各プローブに対応可否を尋ね、対応するものに識別を依頼する。
3. `publish()` がリンクと状態ファイルを書き出す。同じポートに対して以前に別のボード ID で公開されたリンクがあれば、先に削除する。
4. デバイスが外れると `BindsTo=` によりユニットが停止され、その `ExecStop=` が `board-identify remove <port>` を実行する。
5. `board-identify cleanup` は、再起動や異常終了などで取り残されたリンクと状態をさらに掃除する。

## 既知の制約

- プローブは侵襲的です。`esptool` は DTR/RTS を操作するため接続先のボードがリセットされ、同じポートにつながった Espressif 以外のデバイスで動作中のアプリケーションを中断させることがあります。
- 同じノード名がカーネルから別のデバイスへ再割り当てされたあとでは、古くなったリンクを検出できません。この場合は `cleanup` ではなく、そのポートに対する次の `publish()` で解消されます。
- 2 つのポートが同じボード ID を報告した場合、リンクは 1 つを共有します。最後に公開したものが残り、古いポートの状態は次の cleanup で削除されます。

[識別子の形式](identifier-format.ja.md) と [プローブの追加](adding-a-probe.ja.md) も参照してください。
