--
-- Calculate Basic Metrics Tables
--
-- Author: Joseph Lee
-- Company: Ripple Software
-- Email: joseph@ripplesoftware.ca
-- Website: https://www.ripplesoftware.ca
-- Github: https://github.com/rippledj/uspto
--

-- -----------------------------------------------------
-- Table uspto.METRICS_G
-- -----------------------------------------------------

CREATE TABLE IF NOT EXISTS uspto.METRICS_G (
  GrantID VARCHAR(20) NOT NULL,
  ForwardCitCnt INT DEFAULT NULL,
  BackwardCitCnt INT DEFAULT NULL,
  TCT INT DEFAULT NULL,
  FamilySize INT DEFAULT NULL,
  PRIMARY KEY (GrantID));

--
-- Create metrics Record for all GrantID
--
INSERT INTO uspto.METRICS_G (GrantID) SELECT GrantID FROM uspto.GRANT;

--
-- Calculate Forward Citations for all GrantID
--
UPDATE uspto.METRICS_G AS a
SET ForwardCitCnt = t2.count
FROM (SELECT CitedID, count(*) count
FROM uspto.GRACIT_G GROUP BY CitedID) AS t2
WHERE a.GrantID = t2.CitedID;

--
-- Set all patents without FWD citations to 0
--
UPDATE uspto.METRICS_G
SET ForwardCitCnt = 0
WHERE ForwardCitCnt IS NULL;

--
-- Calculate Backward Citations for all GrantID
--
UPDATE uspto.METRICS_G AS a
SET BackwardCitCnt = t2.count
FROM (SELECT GrantID, count(*) AS count
FROM uspto.GRACIT_G GROUP BY GrantID) AS t2
WHERE a.GrantID = t2.GrantID;
--
-- Set all patents without BWD citations to 0
--
UPDATE uspto.METRICS_G
SET uspto.METRICS_G.BackwardCitCnt = 0
WHERE uspto.METRICS_G.BackwardCitCnt IS NULL;
