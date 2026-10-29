from testkart_intelligence.writing.generator import WritingAgent
from testkart_intelligence.writing.qa import QualityAssuranceAgent

writer = WritingAgent()
art_id, art_v_id, c_hash = writer.draft_article(notice_id='not_9b1eef28c437')
print(f"Article created: {art_id}, Version: {art_v_id}, Hash: {c_hash}")

qa = QualityAssuranceAgent()
passed, score, checks = qa.inspect_and_evaluate(art_v_id)
print(f"QA Passed: {passed}, Score: {score}")
for c in checks:
    print(f"  [{'PASS' if c.passed else 'FAIL'}] {c.rule_name} ({c.severity}): {c.message}")
