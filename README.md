# ai-agent-harness-examples

AIエージェントのハーネスと、エージェントが書いたコードに使う品質ゲートの実装例です。

## ディレクトリ

```text
.
├── harness/                  最小のコーディング用ハーネス（Python）
│   ├── harness_common.py     ツール、ガードレール、品質ゲートの共通部分
│   ├── claude_harness.py     Claude Messages API版
│   ├── openai_harness.py     OpenAI Responses API版
│   └── test_harness.py       APIを呼ばない偽クライアントでのテスト
└── quality-gates/            言語別の品質ゲートの設定とproperty testの例
    ├── go/                   golangci-lint v2設定、rapidとfuzzの例、CRAP値とgremlinsの判定スクリプト
    ├── dotnet/               解析・NuGet監査・ロックファイルの設定、CsCheckの例
    └── typescript/           oxlint・oxfmt・pnpm・StrykerJSの設定、fast-checkの例
```

## 動かし方

```sh
# harness
cd harness && python3 -m unittest test_harness.py
pip install -r requirements.txt   # 実APIで動かすとき

# Go
cd quality-gates/go && golangci-lint run ./... && go test ./...

# .NET
cd quality-gates/dotnet && dotnet test QualityGates.slnx

# TypeScript
cd quality-gates/typescript && pnpm install && pnpm lint && pnpm typecheck && pnpm test
```

`quality-gates/typescript` の `pnpm mutation` は、property testだけでは殺せない変異があることを示すため、合格しきい値100を下回って失敗します。

## ライセンス

[MIT](LICENSE)
