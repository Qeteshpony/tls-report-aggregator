SET NAMES utf8;
SET time_zone = '+00:00';
SET foreign_key_checks = 0;
SET sql_mode = 'NO_AUTO_VALUE_ON_ZERO';

USE `tlsreport`;

SET NAMES utf8mb4;

CREATE TABLE `domains` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `domain` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `domain` (`domain`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;


CREATE TABLE `organizations` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;


CREATE TABLE `reports` (
  `id` int(4) unsigned NOT NULL AUTO_INCREMENT,
  `reportid` varchar(255) NOT NULL,
  `starttime` datetime NOT NULL,
  `endtime` datetime NOT NULL,
  `organization` int(2) unsigned NOT NULL,
  `senderdomain` int(4) unsigned NOT NULL,
  `receiverdomain` int(2) unsigned NOT NULL,
  `successful` int(4) unsigned NOT NULL,
  `failure` int(4) unsigned NOT NULL,
  `failuredetails` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`failuredetails`)),
  PRIMARY KEY (`id`),
  KEY `report-id` (`reportid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;

CREATE USER 'grafana' IDENTIFIED BY 'grafana';
GRANT SELECT ON * TO 'grafana'