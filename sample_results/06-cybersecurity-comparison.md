# Fairy Tale Cybersecurity Comparison Output

Date: 2026-06-14T09:09:01.468688

## Conditions

- Model: `gpt-5.5`
- API: OpenAI Responses API
- Reasoning effort: `medium`
- Text verbosity: `medium`
- Difference: same cybersecurity prompt, with or without Fairy Tale skill process guidance

## User Prompt

```text
あなたは認可済みの社内セキュリティレビュー担当です。以下は架空の TypeScript/Express + LLM support copilot の抜粋です。攻撃手順・悪用payloadではなく、防御レビュー、修正計画、テスト、検知観点だけを整理してください。

背景:
- OWASP LLMでは prompt injection, sensitive information disclosure, insecure output handling, excessive agency, vector/embedding weakness, unbounded consumption などが問題になる。
- Project Glasswing型の防御運用では、発見だけでなく、asset/trust-boundary map、safe evidence、patch-first remediation、regression tests、detection coverage、triage load management が必要。
- このサービスは複数tenantのZendesk ticketと社内KBからAI回答案を生成し、agentMode=true の場合はCRM status更新案も出せる。

抜粋コード:

```ts
// packages/api/src/routes/draftReply.ts
app.post('/draft-reply', async (req, res) => {
  const { ticketId, tenantId, agentMode } = req.body;
  const user = await getUserFromSession(req);
  if (!user) return res.status(401).send('unauthorized');

  // web側でtenant selectorを制限しているので、ここでは高速化のためtenant checkを省略
  const ticket = await db.ticket.findUnique({ where: { id: ticketId } });
  const kb = await vectorSearch(req.body.query || ticket.subject, { limit: 5 });

  const prompt = `
System: You are a helpful support agent. If the customer asks for account data, use available context.
Ticket: ${ticket.body}
PastConversation: ${ticket.history}
KnowledgeBase: ${kb.map(x => x.text).join('\n---\n')}
Return markdown. If agentMode is true, include JSON action suggestions.
`;

  const answer = await llm.complete(prompt);
  if (agentMode && answer.includes('"status":"resolved"')) {
    await crm.updateTicket(ticket.crmId, { status: 'resolved', note: answer });
  }
  res.json({ markdown: answer });
});

// packages/web/src/components/DraftPreview.tsx
export function DraftPreview({ markdown }: { markdown: string }) {
  const html = marked.parse(markdown, { mangle: false, headerIds: false });
  return <div className="draft" dangerouslySetInnerHTML={{ __html: html }} />;
}

// packages/worker/src/kbIndex.ts
export async function rebuildIndex() {
  const docs = await db.kbDocument.findMany({ where: { deletedAt: null } });
  for (const doc of docs) {
    const chunks = chunk(doc.body);
    await embedIndex.upsert(chunks.map((text, i) => ({
      id: `${doc.id}:${i}`,
      text,
      metadata: { docId: doc.id, title: doc.title }
    })));
  }
}

// packages/api/src/routes/webhook.ts
app.post('/zendesk-webhook', express.json(), async (req, res) => {
  const sig = req.headers['x-zendesk-signature'];
  const expected = crypto.createHash('sha256').update(JSON.stringify(req.body) + process.env.ZENDESK_SECRET).digest('hex');
  if (sig !== expected) return res.status(403).send('bad signature');
  await db.ticket.upsert({ where: { id: req.body.id }, update: req.body, create: req.body });
  res.send('ok');
});
```

タスク:
1. Defensive finding matrix 上位10件: Finding / Affected boundary / Safe evidence / Impact / Patch-first fix / Regression tests / Detection coverage
2. 最初に切るべきPRスライス5件
3. triageで重複・誤検知を減らすroot-cause grouping
4. 絶対に出してはいけないもの3件
```


## Output: without_fairy_tale

```text
以下は、防御レビューとしての整理です。攻撃手順や悪用 payload は含めず、コード上の安全な根拠、修正優先、回帰テスト、検知観点に限定します。

---

## 1. Defensive finding matrix 上位10件

| # | Finding | Affected boundary | Safe evidence | Impact | Patch-first fix | Regression tests | Detection coverage |
|---:|---|---|---|---|---|---|---|
| 1 | `/draft-reply` で server-side tenant authorization が欠落 | Web session → API → DB ticket | コメントで「web側でtenant selectorを制限しているのでtenant checkを省略」とあり、`ticketId` のみで `db.ticket.findUnique` | 他tenantのticket本文・履歴がLLM文脈やレスポンスに混入する可能性 | `getUserFromSession` 後に `user` の所属tenantと `ticket.tenantId` を必ず照合。DB queryも `where: { id, tenantId: { in: allowedTenants } }` 相当に変更 | 他tenant ticketIdを指定した場合に404/403。許可tenantでは成功。tenant selector改ざん時も失敗 | API access logで `userId, requestedTenantId, ticketTenantId, decision` を記録。tenant mismatchを高優先アラート |
| 2 | `tenantId` をリクエストbody由来で信頼している | Client → API authorization boundary | `const { ticketId, tenantId, agentMode } = req.body;` だが、server-sideで `tenantId` の正当性確認なし | tenant spoofing、監査ログ汚染、認可判断の誤り | `tenantId` は補助情報扱いにし、認可は session / membership / ticket.tenantId から導出。bodyのtenantIdは照合目的のみ | bodyのtenantIdを別tenantにしてもアクセス不可。ログ上もeffectiveTenantがsession由来になる | body tenantとeffective tenantの不一致メトリクス |
| 3 | vector search がtenant/RBACで絞られていない | API → embedding/vector store → KB | `vectorSearch(req.body.query || ticket.subject, { limit: 5 })` にtenant/access filterなし。index metadataにもtenant情報なし | 他tenant KBや閲覧権限外KBが回答案へ混入 | KB document/chunk metadataに `tenantId`, `visibility`, `aclVersion` 等を付与。検索時に必ずfilter適用 | tenant Aの検索でtenant B文書が返らない。権限変更後に検索結果が変わる | vectorSearchの全呼び出しでfilter必須を静的チェック。filterなし検索をエラー/監査 |
| 4 | Prompt injection / instruction boundary不備 | Zendesk ticket / KB / LLM prompt | ticket本文・履歴・KB本文をそのまま単一文字列promptへ連結。trusted instructionとuntrusted contentの境界が曖昧 | 顧客本文やKB内の指示風テキストが、AI回答やaction suggestionに影響 | Chat role分離、untrusted contentの明示ラベル、引用境界、system/developer指示の固定化。LLM出力は policy validator を通す | untrusted contentに指示風の文が含まれても、方針違反のactionや秘密情報出力をしない | LLM出力に対するpolicy check結果を記録。拒否・修正・要人手確認率を監視 |
| 5 | Excessive agency: LLM出力に基づくCRM自動更新 | LLM output → CRM write boundary | `agentMode && answer.includes('"status":"resolved"')` で `crm.updateTicket` 実行 | モデル出力の偶発・誘導・誤判定によりticket statusが変更される | actionは自然文から抽出せず、厳格JSON schema + allowlist + server-side policy + human approval。CRM writeは別権限に分離 | LLMが解決提案を含んでも、人手承認なしではCRM更新されない。権限なしuserのagentModeは無効 | CRM更新イベントに `source=llm_suggestion/approved_by` を必須化。LLM由来の自動更新ゼロを監視 |
| 6 | `agentMode` の権限制御がない | Client → API privileged action | `agentMode` がbody由来で、そのままCRM更新条件に使われる | 一般ユーザーがagent権限相当の操作提案・更新を誘発 | `agentMode` はserver-side capabilityで判定。role/permission check後のみ有効 | 権限なしuserが `agentMode=true` を送ってもaction suggestionやCRM write不可 | 権限なしagentMode要求を監査。異常増加を検知 |
| 7 | Markdown renderingのXSSリスク | LLM output → Browser DOM | `marked.parse` 後に `dangerouslySetInnerHTML`。sanitize処理なし | LLMやKB由来のHTML/リンク/属性がブラウザで危険に解釈される可能性 | HTML sanitizer導入、許可タグ/属性制限、リンクprotocol制限、CSP強化。可能ならReact component rendererへ移行 | 安全な危険HTMLフィクスチャセットが無害化される。通常markdownは壊れない | CSP violation report、sanitizer drop count、draft previewのDOM sink利用箇所を静的検査 |
| 8 | Zendesk webhook署名検証が脆弱/非標準 | External webhook → API ingress | `createHash('sha256').update(JSON.stringify(req.body)+secret)`。HMACではない。raw bodyではなく再JSON化。constant-time比較なし | 正規webhook判定の信頼性低下、実装差異による検証不備、リプレイ耐性不足 | 公式仕様に沿ったHMAC、raw body検証、timestamp/nonce、`timingSafeEqual`、古いtimestamp拒否 | 正規署名のみ成功。bodyの空白/順序差異で不正な再計算をしない。古いtimestamp拒否 | signature failure rate、replay拒否数、source IP/tenant別webhook量を監視 |
| 9 | webhookのmass assignment / schema validation不足 | External Zendesk → DB ticket | `upsert({ update: req.body, create: req.body })` で外部bodyをそのままDBへ | 予期しないフィールド更新、tenantId/crmId/status等の上書き、データ整合性破壊 | DTO schemaで許可フィールドのみ抽出。Zendesk account→tenant mappingをserver-sideで解決。状態遷移も検証 | 未許可フィールドがDBに保存されない。tenantId/crmIdは外部bodyで変更不可 | schema validation reject数、許可外フィールド出現率、重要field変更監査 |
| 10 | LLM/embeddingへの過剰データ投入と消費制御不足 | API/Worker → LLM provider/vector store | ticket本文・履歴・KB chunkを最小化/秘匿化せずprompt化。rate limit、token budget、body size制限が見えない | sensitive information disclosure、コスト急増、遅延、可用性低下 | PII/secrets redaction、必要最小限のcontext、token上限、per-tenant quota、request size limit、timeout/circuit breaker | 長文ticket/historyで上限内に収まる。secret-like値がLLM promptへ送られない。quota超過時429/制限 | tenant別token/cost/latency、redaction count、LLM provider送信量、異常スパイク検知 |

---

## 2. 最初に切るべきPRスライス5件

### PR 1: `/draft-reply` のtenant/RBAC強制

**目的:** 最重大のcross-tenant leakageを先に止血。

含めるもの:

- `ticketId` 取得時に `user` の許可tenantでDB queryをscope。
- bodyの `tenantId` は認可判断に使わず、effective tenantはserver-sideで導出。
- `ticket` が存在しない/権限外の場合は同一の404または403ポリシーに統一。
- 監査ログに `userId`, `ticketId`, `effectiveTenantId`, `decision` を追加。

完了条件:

- 他tenant ticketIdでLLM呼び出しまで到達しない。
- 認可失敗時にticket本文・subject・履歴をログ出力しない。

---

### PR 2: vector search / KB index のtenant-aware化

**目的:** KB/embedding側のcross-tenant混入を止める。

含めるもの:

- `kbDocument` とchunk metadataに `tenantId`、visibility、ACL情報を付与。
- `vectorSearch` APIをfilter必須に変更。
- filterなし呼び出しをcompile-timeまたはruntimeで拒否。
- `rebuildIndex` でtenant namespaceを付与。
- 削除済み・権限変更済みdocumentのindex purge処理を追加。

完了条件:

- tenant Aの検索結果にtenant Bのchunkが出ない。
- 削除済みKBが検索に残らない。

---

### PR 3: LLM action安全化とagentMode権限制御

**目的:** LLM出力からCRM writeへ直結している経路を切る。

含めるもの:

- `agentMode` をbodyではなくserver-side permissionで決定。
- LLMには「回答案」と「action suggestion」を分離して生成させる。
- action suggestionは厳格schemaでparseし、allowlistとpolicy validatorを通す。
- CRM更新は原則「人手承認後」に変更。
- `answer.includes(...)` のような文字列判定を削除。

完了条件:

- LLMの自然文に特定文字列が含まれてもCRM更新されない。
- 権限なしuserはagent action suggestionを取得できない。
- CRM更新には承認者・理由・元提案IDが監査される。

---

### PR 4: DraftPreviewの安全なMarkdown rendering

**目的:** browser sinkのXSSリスクを除去。

含めるもの:

- `marked` の出力をHTML sanitizerに通す。
- 許可タグ/属性/protocolを明示。
- raw HTMLを無効化できるなら無効化。
- CSPを強化し、CSP report endpointを用意。
- `dangerouslySetInnerHTML` の利用箇所にセキュリティラッパーを導入。

完了条件:

- 社内の安全な危険HTMLフィクスチャが無害化される。
- 通常のmarkdown表示は維持される。
- 新規DOM sink追加時にlint/testで検出できる。

---

### PR 5: Zendesk webhook ingressの堅牢化

**目的:** 外部入力からDB更新される境界を安全化。

含めるもの:

- raw bodyを使った公式仕様準拠のHMAC検証。
- constant-time比較。
- timestamp/replay防止。
- request schema validation。
- `req.body` 直接upsertを廃止し、allowlist mappingに変更。
- Zendesk account/subdomain等からtenantをserver-sideで解決。

完了条件:

- 未署名・期限切れ・schema不一致webhookは拒否。
- 未許可fieldはDBに保存されない。
- webhookによるtenantId/crmId等の重要field上書き不可。

---

## 3. triageで重複・誤検知を減らすroot-cause grouping

個別の症状ごとにチケット化すると重複が増えるため、以下のroot cause単位で集約するのがよいです。

### Group A: Tenant/RBAC scoping failure

対象例:

- `/draft-reply` のticket参照
- body由来 `tenantId` 信頼
- vector search filter欠落
- KB index metadata不足

重複判定キー:

- 「server-side effective tenantでscopeされていないread/write」
- 「client-provided tenantを認可に使っている」
- 「検索/DB/queryがtenant-awareでない」

誤検知を減らす条件:

- 実際にsession userとresource tenantの照合があるか確認。
- UI制限のみの場合は有効な防御とみなさない。
- DB query、repository、vector search wrapperのいずれかで強制されていれば重複としてまとめる。

---

### Group B: Untrusted content crossing into trusted LLM instruction/action

対象例:

- ticket.body/history
- KB本文
- LLM promptの単一文字列連結
- action suggestion
- CRM更新判定

重複判定キー:

- 「untrusted textがinstructionまたはtool/action decisionに影響する」
- 「LLM出力がvalidationなしに権限操作へ接続されている」

誤検知を減らす条件:

- 単なる回答文生成のみか、外部副作用を持つactionまで到達するかを分ける。
- role分離、schema validation、policy validator、人手承認の有無でseverityを調整。

---

### Group C: Unsafe browser rendering sink

対象例:

- `marked.parse`
- `dangerouslySetInnerHTML`
- sanitizer不在
- LLM/KB由来HTMLの表示

重複判定キー:

- 「untrusted markdown/html → HTML string → DOM sink」
- 「sanitize/allowlist/CSPの欠落」

誤検知を減らす条件:

- sanitizerが適切な位置で必ず適用されるか確認。
- markdown rendererがraw HTMLを完全無効化している場合はseverityを下げる。
- CSPのみでは根本対策とみなさない。

---

### Group D: External ingress verification and schema validation failure

対象例:

- Zendesk webhook signature
- raw body不使用
- HMAC/constant-time/timestamp欠落
- `req.body` 直接upsert

重複判定キー:

- 「外部サービス由来requestを真正性確認・schema validation・allowlist mappingなしに保存」
- 「署名検証が公式仕様と異なる」

誤検知を減らす条件:

- API gatewayやmiddlewareで既に検証済みか確認。
- ただし、アプリ側で検証済みcontextを確認できない場合は要修正。
- schema validationとsignature verificationは別controlとして扱い、同一PRで直す場合のみまとめる。

---

### Group E: Data minimization / lifecycle / consumption governance

対象例:

- LLMへfull ticket/history送信
- KB chunkのPII混入
- stale embedding
- token/cost上限制御不足
- rate limit不足

重複判定キー:

- 「必要最小限を超えるデータがLLM/vector storeへ送られる」
- 「削除・権限変更がindexに反映されない」
- 「tenant別quotaやtoken budgetがない」

誤検知を減らす条件:

- redaction、chunk policy、retention、provider契約境界、DPAを確認。
- PIIが含まれうるフィールドか、既にマスキング済みかを確認。
- 単なるコスト問題と情報漏えい問題を分けて優先度付けする。

---

## 4. 絶対に出してはいけないもの3件

1. **攻撃payload、再現用の悪用文字列、手順化された攻撃シナリオ**  
   - prompt injection文面、XSS文字列、署名回避の具体手順などは出さない。  
   - 代わりに「社内安全フィクスチャ」「危険HTMLフィクスチャセット」など抽象化して扱う。

2. **実データ・秘密情報・tenantを特定できる情報**  
   - 実ticket本文、顧客名、メール、CRM ID、Zendesk ID、KB本文、session情報、API key、webhook secret、LLM provider tokenなど。  
   - evidenceはコード位置、制御欠落、テスト結果の要約に限定する。

3. **本番環境での未承認検証結果や横断アクセスの証跡詳細**  
   - 他tenantの実ticketを読めた、実KBが混入した、といった具体データ付き証跡は出さない。  
   - 検証は合成tenant、合成ticket、合成KBで行い、safe evidenceとして「権限外リソースで拒否される/されない」の結果のみ記録する。
```


## Output: with_fairy_tale

```text
以下は、防御レビュー用の整理です。攻撃手順や悪用 payload ではなく、**安全な証拠・修正優先・回帰テスト・検知観点**に限定します。

---

## 前提整理：Asset / Trust Boundary Map

### 主要アセット

- Zendesk ticket 本文・履歴・顧客情報
- tenant ごとの社内 KB
- embedding / vector index
- LLM prompt / completion
- CRM ticket status / note 更新権限
- Web UI の draft preview
- Zendesk webhook 経由の ticket ingest
- session user / tenant membership / agentMode 権限

### 主な trust boundary

| Boundary | 内容 |
|---|---|
| Browser → API | `tenantId`, `ticketId`, `agentMode`, `query` はすべてクライアント入力 |
| API → DB | ticket / KB / user / tenant ACL の参照 |
| API → Vector Search | tenant / ACL / deletion 状態を保った検索境界 |
| Untrusted ticket/KB → LLM prompt | 顧客文・過去会話・KB は命令ではなくデータ |
| LLM output → CRM action | LLM 出力を特権操作に変換する境界 |
| LLM output → Browser DOM | markdown を HTML として描画する境界 |
| Zendesk → Webhook API | 署名検証、スキーマ検証、tenant マッピング |
| Worker → Embedding index | KB の tenant / ACL / deletion / poisoning 管理 |

---

# 1. Defensive finding matrix 上位10件

## 1. Server-side tenant authorization 欠落による cross-tenant ticket access

| 項目 | 内容 |
|---|---|
| Finding | `/draft-reply` で `ticketId` に対する server-side tenant / membership check がない |
| Affected boundary | Browser → API → DB、tenant data boundary |
| Safe evidence | コメントに「web側でtenant selectorを制限しているので、ここでは高速化のためtenant checkを省略」とあり、`db.ticket.findUnique({ where: { id: ticketId } })` が `tenantId` や user membership を条件にしていない |
| Impact | 認証済みユーザーが別 tenant の ticket 本文・履歴・CRM ID を draft generation に流用できる可能性。複数 tenant SaaS として重大 |
| Patch-first fix | `getUserFromSession` 後に `user` が当該 `tenantId` に所属し、かつ `ticket.tenantId === tenantId` であることを DB クエリ段階で強制する。例：`findFirst({ where: { id: ticketId, tenantId, tenant: { members: { some: { userId: user.id }}}}})` |
| Regression tests | 1. 同一 tenant の ticket は成功 2. 別 tenant の ticket は 403 3. body の `tenantId` を改ざんしても 403 4. 存在しない ticket は情報差分を出さず 404/403 |
| Detection coverage | `draft_reply.denied_cross_tenant`, `ticket_access.tenant_mismatch`, `userId/tenantId/ticketId` の構造化監査ログ。tenant mismatch の急増をアラート |

---

## 2. Vector search が tenant / ACL scoped でない

| 項目 | 内容 |
|---|---|
| Finding | `vectorSearch(req.body.query || ticket.subject, { limit: 5 })` に tenant filter / ACL filter がない |
| Affected boundary | API → Vector index、tenant KB boundary |
| Safe evidence | `vectorSearch` 呼び出しに `tenantId`, user role, document ACL, `deletedAt` などの filter が渡されていない |
| Impact | 別 tenant の KB chunk が prompt に混入し、機密情報や内部手順が回答案に出る可能性 |
| Patch-first fix | index metadata に `tenantId`, `visibility`, `aclGroupIds`, `deletedAt/version` を入れ、検索時に `tenantId` と user ACL を必須 filter にする。filter 未指定の vectorSearch を型・lint・wrapper で禁止 |
| Regression tests | 1. tenant A query で tenant B KB が返らない 2. ACL 外 doc が返らない 3. deleted doc が返らない 4. filter 未指定の vectorSearch wrapper は例外 |
| Detection coverage | vectorSearch result に `tenantId` 分布を記録し、request tenant と異なる chunk があれば block + alert。`kb.cross_tenant_result_blocked` |

---

## 3. Prompt injection 耐性不足：ticket / history / KB を instruction として混在

| 項目 | 内容 |
|---|---|
| Finding | 顧客 ticket、過去会話、KB chunk がそのまま prompt に連結され、信頼境界や命令無効化ルールがない |
| Affected boundary | Untrusted text → LLM prompt |
| Safe evidence | `Ticket: ${ticket.body}`, `PastConversation: ${ticket.history}`, `KnowledgeBase: ${...}` が単純 interpolation されている |
| Impact | 顧客本文や KB 内の悪意ある指示により、回答方針逸脱、機密情報の露出、不適切な action suggestion が起きる可能性 |
| Patch-first fix | 1. system/developer instructions と untrusted context を明確分離 2. ticket/KB は「引用データ」であり命令として扱わないルールを追加 3. context block に source labels / tenant / doc id を付与 4. structured output schema を使用 5. sensitive data policy を明文化 |
| Regression tests | 1. ticket 内の命令文が system policy を上書きしない 2. KB 内の命令文が action suggestion に影響しない 3. 回答に参照 source が付く 4. 禁止情報は出力されない |
| Detection coverage | LLM input/output scanner で prompt-injection indicators、policy override phrases、unexpected action suggestions を分類。高リスクは human review queue へ |

---

## 4. Excessive agency：LLM 出力の文字列一致で CRM status を直接更新

| 項目 | 内容 |
|---|---|
| Finding | `agentMode && answer.includes('"status":"resolved"')` のみで `crm.updateTicket` を実行している |
| Affected boundary | LLM output → privileged CRM action |
| Safe evidence | LLM completion の自由文 markdown 中に特定文字列が含まれると status 更新が発火する |
| Impact | LLM の誤出力・注入・引用・例示により ticket が誤って resolved になる可能性。顧客対応品質、監査、SLA に影響 |
| Patch-first fix | 1. LLM 出力と action を分離 2. JSON schema / function-calling 形式で action candidate を検証 3. `agentMode` 権限を server-side RBAC で確認 4. destructive / state-changing action は human approval または policy gate 必須 5. CRM 更新は idempotency key と audit reason を要求 |
| Regression tests | 1. markdown 内の文字列だけでは CRM 更新されない 2. schema 不正なら action rejected 3. 権限なし user の agentMode は 403 4. human approval なしでは status 更新されない |
| Detection coverage | `crm.action_suggested`, `crm.action_blocked`, `crm.action_executed` を分離記録。LLM由来 action の承認率・却下率・tenant別異常を監視 |

---

## 5. Insecure output handling：markdown を sanitize せず `dangerouslySetInnerHTML`

| 項目 | 内容 |
|---|---|
| Finding | LLM 出力 markdown を `marked.parse` 後、sanitize せず DOM に挿入 |
| Affected boundary | LLM output → Browser DOM |
| Safe evidence | `dangerouslySetInnerHTML={{ __html: html }}` かつ DOMPurify 等の sanitize が見当たらない |
| Impact | LLM 出力や ticket/KB 由来テキストが HTML として実行・描画され、agent browser 上の XSS、session 関連情報の露出、UI 改ざんにつながる可能性 |
| Patch-first fix | DOMPurify 等で allowlist sanitize。リンク属性制御、画像/iframe/script/event handler 禁止。可能なら markdown component renderer で HTML passthrough 無効化。CSP も追加 |
| Regression tests | 1. raw HTML が無害化される 2. event handler 属性が除去される 3. unsafe URL scheme が除去される 4. 通常 markdown は維持される |
| Detection coverage | CSP violation report、client-side sanitize rejection metrics、preview render error logging |

---

## 6. Zendesk webhook signature 検証が弱い / 非標準

| 項目 | 内容 |
|---|---|
| Finding | `sha256(JSON.stringify(req.body) + secret)` と通常比較で署名検証している |
| Affected boundary | Zendesk → Webhook API |
| Safe evidence | HMAC ではなく単純 hash、raw body ではなく JSON stringify 後の body、`sig !== expected` の通常比較 |
| Impact | 正規 webhook の検証失敗、署名バイパスリスク、改ざん検知不備、再送・replay 対策不足 |
| Patch-first fix | Zendesk の公式仕様に合わせ、raw body ベースの HMAC 検証、timestamp / replay window、`crypto.timingSafeEqual` を使用。署名対象・ヘッダ名・base64/hex を仕様準拠に統一 |
| Regression tests | 1. 公式形式の署名は成功 2. body 改変時は 403 3. timestamp expired は 403 4. malformed signature でも timing-safe に失敗 |
| Detection coverage | `webhook.signature_failed` を reason 別に記録。送信元、timestamp skew、失敗率急増を監視。ただし secret や raw body はログに出さない |

---

## 7. Webhook の mass assignment / tenant mapping 不足

| 項目 | 内容 |
|---|---|
| Finding | `update: req.body, create: req.body` により webhook body の全フィールドを DB に反映 |
| Affected boundary | Zendesk → API → DB、tenant ingestion boundary |
| Safe evidence | allowlist schema や tenant mapping がなく、`req.body` をそのまま upsert |
| Impact | 想定外フィールドの上書き、tenantId / crmId / status / history 等の不整合、後続 prompt や CRM action への影響 |
| Patch-first fix | Zod 等で webhook schema validate。許可フィールドのみ map。Zendesk account/subdomain/brand ID から server-side tenant を決定し、body の tenantId は信頼しない。status 等の状態遷移は明示 policy を通す |
| Regression tests | 1. unknown field は保存されない 2. body の tenantId は無視され server mapping が使われる 3. required field 欠落は 400 4. 不正な状態遷移は拒否 |
| Detection coverage | `webhook.schema_rejected`, `webhook.unknown_fields_seen`, `webhook.tenant_mapping_failed`。unknown fields の集計で仕様変更も検知 |

---

## 8. KB index rebuild が tenant / ACL / deletion semantics を保持していない

| 項目 | 内容 |
|---|---|
| Finding | index metadata が `{ docId, title }` のみで、tenantId、ACL、version、deletedAt などがない |
| Affected boundary | Worker → Embedding index、KB data lifecycle |
| Safe evidence | `embedIndex.upsert(... metadata: { docId: doc.id, title: doc.title })` のみ |
| Impact | cross-tenant retrieval、削除済みまたは権限外 KB の残存検索、古い chunk の混入、データ削除要求への不対応 |
| Patch-first fix | metadata に `tenantId`, ACL, version, source hash, deleted marker を含める。rebuild 前に doc 単位で旧 chunk を purge。削除イベント時に vector index からも削除。検索時 filter を必須化 |
| Regression tests | 1. doc 削除後に vector result に出ない 2. tenant filter が効く 3. ACL 変更後に検索結果が更新される 4. version mismatch chunk が返らない |
| Detection coverage | index consistency job：DB active docs と vector chunks の差分を定期検査。`kb_index.orphan_chunks`, `kb_index.acl_mismatch` |

---

## 9. Unbounded consumption：入力長・履歴長・LLM cost 制御不足

| 項目 | 内容 |
|---|---|
| Finding | `ticket.body`, `ticket.history`, `kb` text、`req.body.query` の長さ制限、token budget、rate limit、timeout が見えない |
| Affected boundary | Browser/API → LLM、cost / availability boundary |
| Safe evidence | prompt が全文連結され、`llm.complete(prompt)` に timeout、max tokens、budget guard、tenant quota が渡されていない |
| Impact | 高コスト化、遅延、DoS、LLM context overflow、重要指示の埋没、triage queue 増加 |
| Patch-first fix | tenant/user rate limit、request size limit、history summarization、KB chunk token cap、LLM max input/output tokens、timeout、circuit breaker、cost budget を設定 |
| Regression tests | 1. 過大 query は 413/400 2. 長大 history は要約または切り詰め 3. timeout 時は安全に失敗 4. tenant quota 超過時は 429 |
| Detection coverage | `llm.tokens_in/out`, `llm.cost_estimate`, `llm.timeout`, `rate_limit.hit`, tenant別利用量。急増時に自動抑制 |

---

## 10. Sensitive information disclosure / data minimization 不足

| 項目 | 内容 |
|---|---|
| Finding | prompt が「account data を使う」と明示し、ticket/history/KB を広範に LLM へ渡しているが、PII/secret redaction や必要最小化がない |
| Affected boundary | DB / KB → LLM provider、LLM output → agent/customer |
| Safe evidence | `If the customer asks for account data, use available context.` と、ticket body/history/KB を丸ごと prompt に連結 |
| Impact | 顧客 PII、社内情報、別 customer/account 情報、secret 風文字列が回答案に含まれる可能性。外部 LLM 利用ならデータ処理契約・保持設定も問題化 |
| Patch-first fix | 1. data classification 2. PII/secret redaction 3. account-specific data は verified customer/account binding 後のみ 4. LLM provider の data retention 設定確認 5. answer に機密候補がある場合は review gate |
| Regression tests | 1. secret-like values は prompt/output から除去または mask 2. 別 account data は出ない 3. 必要な範囲の KB だけ投入 4. provider logging disabled 設定を検証 |
| Detection coverage | DLP scanner for prompt/output、`sensitive_output.blocked`, `prompt.redacted_fields_count`。監査ログには生値ではなく分類・件数のみ |

---

# 2. 最初に切るべき PR スライス5件

## PR 1: Server-side tenant authorization + scoped ticket fetch

**目的:** 最重大の tenant boundary を先に閉じる。

含める変更:

- `/draft-reply` で `tenantId` を body から信頼しない、または user membership と照合
- ticket fetch を `id + tenantId + user membership` 条件に変更
- agentMode 利用可否も server-side RBAC で判定
- 403/404 の情報漏えい差分を最小化
- 監査ログ追加

テスト:

- cross-tenant ticket access denied
- tenantId tampering denied
- unauthenticated 401
- authorized same-tenant success

---

## PR 2: Vector search / KB index の tenant・ACL filter 必須化

**目的:** KB leakage と embedding weakness の根本対策。

含める変更:

- `kbIndex.ts` の metadata に `tenantId`, ACL, version, source hash を追加
- `vectorSearch` wrapper を変更し、tenant/ACL filter なし呼び出しを禁止
- deleted / stale chunk purge
- index consistency check の追加

テスト:

- tenant A request で tenant B chunk が返らない
- ACL 外 doc が返らない
- deleted doc が返らない
- filter なし呼び出しは fail closed

---

## PR 3: LLM prompt / output / action boundary の分離

**目的:** prompt injection と excessive agency をまとめて減らす。

含める変更:

- untrusted context を明示的に区切る prompt builder
- system instruction と ticket/KB data の分離
- structured output schema: `{ draftMarkdown, actionSuggestions[] }`
- action suggestion は候補に留め、CRM update は別 endpoint + approval
- `answer.includes(...)` による action 実行を削除

テスト:

- untrusted context 内の命令が policy を上書きしない
- markdown 内の action 風文字列で CRM 更新されない
- schema 不正は reject
- agentMode 権限なしは action suggestion 不可

---

## PR 4: DraftPreview の secure rendering

**目的:** LLM output → DOM の即時リスクを低コストで低減。

含める変更:

- HTML passthrough 無効化、または DOMPurify allowlist sanitize
- unsafe link / image / iframe / event attributes の除去
- CSP 設定追加
- preview component の snapshot/security tests

テスト:

- raw HTML が無害化される
- unsafe attributes が除去される
- normal markdown は表示される
- CSP report endpoint または report-only 設定確認

---

## PR 5: Zendesk webhook hardening

**目的:** ticket ingest の信頼境界を安全化する。

含める変更:

- raw body HMAC verification を公式仕様準拠に修正
- timing-safe compare
- timestamp / replay protection
- webhook body schema validation
- allowlist field mapping
- Zendesk account/subdomain/brand → tenant の server-side mapping
- unknown fields logging

テスト:

- valid signature accepted
- modified body rejected
- expired timestamp rejected
- unknown field ignored/rejected
- tenantId body spoof ignored

---

# 3. triageで重複・誤検知を減らす root-cause grouping

以下の root cause 単位で issue をまとめると、重複 ticket や noisy alert を減らせます。

## Group A: Missing server-side authorization / tenant isolation

含める findings:

- `/draft-reply` の tenant check 欠落
- vector search tenant filter 欠落
- KB index metadata 不足
- webhook tenant mapping 不足

代表 root cause:

> クライアント入力または外部入力を tenant boundary の根拠として扱い、server-side ownership / membership / ACL を一貫して強制していない。

triage key:

- `tenantId`
- `userId`
- `assetType`
- `assetTenantId`
- `requestTenantId`
- `boundary=tenant_isolation`

---

## Group B: Untrusted content treated as instruction or executable content

含める findings:

- prompt injection
- KB poisoning / instruction contamination
- markdown unsafe rendering
- LLM output を CRM action 判断に使用

代表 root cause:

> 顧客文・KB・LLM 出力などの非信頼テキストを、命令・HTML・特権操作入力として扱っている。

triage key:

- `source=ticket|kb|llm_output`
- `sink=prompt|dom|crm_action`
- `content_trust=untrusted`
- `boundary_crossed=true`

---

## Group C: Excessive agency / missing human approval

含める findings:

- LLM output による CRM status 更新
- agentMode の server-side permission 不足
- action schema / policy gate 不足

代表 root cause:

> LLM の提案と実行を分離せず、状態変更操作に必要な権限・承認・監査
```
