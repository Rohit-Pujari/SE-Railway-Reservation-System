-- Issue #27: persist explicit train-to-route assignments.
-- Run once on databases created before this issue was implemented.
CREATE TABLE IF NOT EXISTS train_routes (
  train_id BIGINT UNSIGNED NOT NULL,
  route_id BIGINT UNSIGNED NOT NULL,
  assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (train_id, route_id),
  KEY idx_train_routes_route (route_id, train_id),
  CONSTRAINT fk_train_routes_train FOREIGN KEY (train_id)
    REFERENCES trains (train_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_train_routes_route FOREIGN KEY (route_id)
    REFERENCES routes (route_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;
