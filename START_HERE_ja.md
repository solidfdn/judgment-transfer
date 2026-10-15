# Judgment Transfer：担当者向け運用手順

**専任担当者の資料や説明をもとに、AIに任せられる範囲を確かめます。**

足りない情報や、人の判断が必要な箇所を明らかにし、後任担当者への引継ぎにも活かせます。

- [アプリ](https://judgment-transfer-unql76xapq-an.a.run.app/)
- [保存済みの結果を使った説明用デモ](https://judgment-transfer-unql76xapq-an.a.run.app/assets/demo/index.html)
- [英語の操作・環境構築ガイド](START_HERE.md)

## 画面での操作

1. **Job and intended result** に対象業務と目的を記入します。**Upload file** で資料を入れ、**Explanation or comment** に補足を書いて **Add explanation** で保存します。
2. **Organize the work** で確認事項を読みます。**Prepare a practice test** から検証条件を作り、内容を確認して承認します。
3. 案件の事実・初期状態を確認して保存し、**Try the original instructions** で試します。
4. **Find what needs explaining** の質問に回答し、作成された補足条件を確認・承認します。**Try the same cases with the guidance** で変化を確かめます。
5. **Responsible person** に担当者名を記入します。任意のメモを添えて結果を確定すると、資料・説明・判断・日時を版として保存できます。**Decision history** から以前の記録を開き、比較や確認付き削除を行えます。

## 既存環境を更新する

案内された更新スクリプトをCloud ShellのHOMEに保存し、既存のフォルダで実行します。1.0.33の更新コマンドは次のとおりです。

```bash
cd "$HOME/Judgment_Transfer_Runbook_v1.0" &&
python3 "$HOME/jt_release_133.py" --deploy
```

更新プログラムは元のファイルを照合し、変更対象をバックアップしてデプロイします。`.jt`、既存の資料・承認・検証結果・利用量を保持します。デプロイ後の照合結果と表示URLを確認してください。

既存の完了済み環境の更新には、初期構築の00〜08を繰り返し実行する必要はありません。新規環境の構築手順は [START_HERE.md](START_HERE.md) にまとめています。

## 状態確認と停止時の対応

```bash
cd "$HOME/Judgment_Transfer_Runbook_v1.0" &&
bash jt status
bash jt support
```

`support` は版・工程・停止理由をまとめた共有用の診断を出力します。認証情報や素材本文を含むログ全体を共有する必要はありません。停止理由を確認してから、該当する更新スクリプトまたは停止した工程を再開します。

初期構築の番号付き工程が失敗した場合のみ、例えば04なら `bash jt 04 --retry` で再開します。更新スクリプトの失敗には、その更新スクリプトの再開手順を使います。

現環境のモデル利用上限は、承認済みの累計100ドルです。保存済みの利用量を引き継ぎます。Cloud Run等の基盤費用は別です。公開アクセスを停止する場合は `bash jt close` を実行します。

## 提出物の確認

完成した画面と実行結果に合わせて、公開アプリURL、公開GitHub、3分未満の実画面動画、英語PDFを揃えます。提出後は受付結果を確認します。詳細な変更・検証記録は [CHANGELOG.md](CHANGELOG.md) と [verification/](verification/) にあります。
