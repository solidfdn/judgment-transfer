# Judgment Transfer：操作・運用ガイド

[English setup and operation guide](START_HERE.md)

Judgment Transferを試すには、[アプリ](https://judgment-transfer-unql76xapq-an.a.run.app/)を開いてください。[説明用デモ](https://judgment-transfer-unql76xapq-an.a.run.app/assets/demo/index.html)では、v1.0.39で記録した経費書類の比較結果を確認できます。社員個人宛て領収書の受入条件を担当者が承認するとSamの案件が進む一方、支払情報の不足や滞在日程の変更がある案件は保留を続けます。詳細は[事例と検証方法](README.md#a-concrete-example-expense-document-checks)をご覧ください。

## 画面での操作

1. **Job and intended result** に対象業務と目的を記入します。**Upload file** で資料を入れるか、**Explanation or comment** に説明を書いて **Add explanation** で保存します。
2. **Organize the work** で確認事項と根拠を読みます。**Prepare a practice test** から検証条件の案を作成します。
3. **Responsible person** に担当者名を記入し、条件を確認して承認します。案件ファイルを読み込むか手入力で例を追加し、各案件の事実と初期状態を確認・確定します。
4. **Try the original instructions** で試します。画面のステップ2に進み、**Find what needs explaining** の質問に回答して **Draft the guidance** を選びます。作成された補足条件を確認・承認します。
5. **Try the same cases with the guidance** で前後の結果と各案件の根拠を確認します。**Finalize this result** で確定すると、担当者名・日時・任意のメモとともに結果を記録できます。

資料はTXT、テキストPDF、PNG/JPEG、短いMP4に対応し、合計5ファイル・20 MiBまで追加できます。ファイル別の上限はアップロード欄に表示されます。読み取られた事実は確定前に確認し、不明な項目は不明のまま扱います。検証中の操作は、隔離された練習用の案件状態に反映されます。

**Continue saved work** は同じタブで以前開いた作業を再開します。**Saved tests** は過去の検証結果を開きます。**Decision history** では確定済みの記録と版の比較を確認できます。確定済みの記録は編集できず、選択した記録の削除や履歴のリセットには確認が必要です。

## ローカル実行・新規環境の構築

Python 3.12によるローカルのシミュレーションと、Google Cloud Shellによる新規環境の構築手順は [START_HERE.md](START_HERE.md) にまとめています。Geminiによる資料の確認や条件案の作成にはLIVE環境を使います。承認後の案件には、アプリ内のルールエンジンで条件を適用します。

モデル利用とCloud Run等の基盤利用には料金が発生します。モデルの利用上限は、各環境に保存された設定に従います。

## 既存環境を更新する

既存環境の版に対応する更新スクリプトと、その版の手順を使用します。案内されたスクリプトをCloud ShellのHOMEに保存し、既存のフォルダで実行してください。適用前の版と進行状態は、下記の `bash jt status` で確認できます。

更新プログラムは元のファイルを照合し、変更対象をバックアップしてデプロイします。`.jt`、既存の資料・承認・検証結果・利用量を保持します。デプロイ後の照合結果と表示URLを確認してください。

既存の完了済み環境の更新には、初期構築の00〜08を繰り返し実行する必要はありません。

配布パッケージとアプリの版は [SPEC_LOCK.json](SPEC_LOCK.json) に分けて記録しています。資料のみの更新では、アプリの版を維持したままパッケージの版が変わることがあります。

## 状態確認と停止時の対応

```bash
cd "$HOME/Judgment_Transfer_Runbook_v1.0" &&
bash jt status
bash jt support
```

`support` は版・工程・停止理由をまとめた共有用の診断を出力します。認証情報や素材本文を含むログ全体を共有する必要はありません。停止理由を確認してから、該当する更新スクリプトまたは停止した工程を再開します。

初期構築の番号付き工程が失敗した場合のみ、例えば04なら `bash jt 04 --retry` で再開します。更新スクリプトの失敗には、その更新スクリプトの再開手順を使います。

`bash jt close` はアプリのデータを削除せず、アクセスを認証必須に戻します。`.jt/`、認証情報、個人の資料、クラウドの生ログをソース管理に含めないでください。
