-- 复核流程补齐（撤回/驳回/修改重提/并发仲裁）与归档快照版本化。
-- 幂等基线：实际启动由 src.config.database.upgrade_schema 按检查信息自动补齐，本文件说明目标结构。
-- 1) reviews 增加 version（重提版本号，默认1）与 created_by（提交人，历史行可为空）。
ALTER TABLE reviews ADD COLUMN version INT NOT NULL DEFAULT 1;
ALTER TABLE reviews ADD COLUMN created_by VARCHAR(160) NOT NULL DEFAULT '';
CREATE INDEX ix_reviews_run_id ON reviews (run_id);
-- 2) review_events 保存每次复核处理意见与操作者，追加写入，不修改不删除。
CREATE TABLE review_events (
 id VARCHAR(36) NOT NULL PRIMARY KEY,
 created_at DATETIME NOT NULL,
 review_id VARCHAR(36) NOT NULL,
 action VARCHAR(20) NOT NULL,
 from_state VARCHAR(20) NOT NULL DEFAULT '',
 to_state VARCHAR(20) NOT NULL DEFAULT '',
 actor VARCHAR(160) NOT NULL DEFAULT '',
 comment TEXT NOT NULL,
 detail JSON NOT NULL,
 CONSTRAINT fk_review_events_review FOREIGN KEY (review_id) REFERENCES reviews (id)
);
CREATE INDEX ix_review_events_review_id ON review_events (review_id);
-- 3) reports.review_id 仍为唯一键：同一复核重复归档返回同一份快照。
