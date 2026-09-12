# Build Flow

```
用户勾选 Data Assets → POST /api/builds/plan
  {title, requirement(来自 agent planning), inputs:[artifact_id]}
→ assets + profiles → BuildPlanner（plan_build_sync / plan_build[LLM]）
→ BuildPlan：entity_strategy / time_strategy / keys（来自 joins）/ field_mappings /
  aggregations（flow=sum, stock=last, rate=mean, unknown=none+NEEDS_REVIEW）/
  missing_policy / derived / review_points
→ blocking review points？→ 202 返回 plan + 审查项 → 用户编辑或 /approve
→ BuildExecutor.from_build_plan(plan) → run()
    entity: country→ISO3 / province→GB省码 / city→GB地级码 / firm·individual→NEEDS_REVIEW
    time: year/date/period/quarter/month → 统一 year
    join: cardinality 检查，m:m 默认阻止，NULL 键不参与
    aggregation: 逐变量（禁止默认 mean）
    missing: 默认 none；任何插补标记 __imputed_*
→ QA（13 类检查）→ Provenance（字段级 lineage）→ Package（CSV/Parquet/XLSX
  + methodology + quality_report + reproduce.py + manifest）
```

无 country/year 硬编码：entity strategy 与 keys 全部由 BuildPlan（基于真实 Profile）决定。
