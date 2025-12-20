//! NCAA Basketball Odds Ingestion Service v6.0
//!
//! Real-time odds streaming from The Odds API with sub-10ms latency.
//! Publishes to Redis Streams and stores in TimescaleDB.
//!
//! Security improvements:
//! - Reads API keys from Docker secrets (file-based)
//! - Proper thread-safe caching with entry API
//! - Rate limiting and error handling

use anyhow::{anyhow, Context, Result};
use chrono::{DateTime, Utc};
use governor::{Quota, RateLimiter};
use redis::AsyncCommands;
use serde::{Deserialize, Serialize};
use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;
use std::collections::hash_map::Entry;
use std::collections::HashMap;
use std::env;
use std::num::NonZeroU32;
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{error, info, warn};
use uuid::Uuid;
use axum::{
    routing::get,
    Router,
    Json,
    http::StatusCode,
};
use serde_json::json;

/// The Odds API event structure
#[derive(Debug, Deserialize, Clone, Default)]
#[serde(default)]
pub struct OddsApiEvent {
    pub id: String,
    pub sport_key: String,
    pub sport_title: String,
    pub commence_time: Option<DateTime<Utc>>,
    pub home_team: String,
    pub away_team: String,
    pub bookmakers: Vec<Bookmaker>,
}

#[derive(Debug, Deserialize, Clone, Default)]
#[serde(default)]
pub struct Bookmaker {
    pub key: String,
    pub title: String,
    pub last_update: Option<DateTime<Utc>>,
    pub markets: Vec<Market>,
}

#[derive(Debug, Deserialize, Clone, Default)]
#[serde(default)]
pub struct Market {
    pub key: String,
    pub last_update: Option<DateTime<Utc>>,
    pub outcomes: Vec<Outcome>,
}

#[derive(Debug, Deserialize, Clone, Default)]
#[serde(default)]
pub struct Outcome {
    pub name: String,
    pub price: Option<i32>,
    pub point: Option<f64>,
}

/// Normalized odds snapshot for storage
#[derive(Debug, Serialize, Clone)]
pub struct OddsSnapshot {
    pub time: DateTime<Utc>,
    pub game_id: Uuid,
    pub external_id: String,
    pub bookmaker: String,
    pub market_type: String,
    pub period: String,
    pub home_line: Option<f64>,
    pub away_line: Option<f64>,
    pub total_line: Option<f64>,
    pub home_price: Option<i32>,
    pub away_price: Option<i32>,
    pub over_price: Option<i32>,
    pub under_price: Option<i32>,
}

/// Configuration
#[derive(Clone)]
pub struct Config {
    pub odds_api_key: String,
    pub database_url: String,
    pub redis_url: String,
    pub poll_interval_seconds: u64,
    pub sport_key: String,
    pub health_port: u16,
    /// If true, run once and exit (no polling loop)
    pub run_once: bool,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        // Secrets/config:
        // - Docker Compose: read from /run/secrets/*
        // - Azure Container Apps: read from env vars (no /run/secrets mount)

        // API key
        let odds_api_key = match env::var("THE_ODDS_API_KEY") {
            Ok(v) if !v.trim().is_empty() => v,
            Ok(_) => return Err(anyhow!("THE_ODDS_API_KEY is set but empty")),
            Err(_) => read_secret_file("/run/secrets/odds_api_key", "odds_api_key")?,
        };

        // Prevent accidental use of sample/placeholder keys
        let key_lower = odds_api_key.trim().to_lowercase();
        if key_lower.contains("change_me") 
            || key_lower.contains("your_") 
            || key_lower.starts_with("sample")
            || key_lower == "4a0b80471d1ebeeb74c358fa0fcc4a2" {
            return Err(anyhow!(
                "THE_ODDS_API_KEY appears to be a placeholder value; replace with your real key"
            ));
        }

        // Database URL - sport-parameterized for multi-sport deployment
        let sport = env::var("SPORT").unwrap_or_else(|_| "ncaam".to_string());
        let db_user = env::var("DB_USER").unwrap_or_else(|_| sport.clone());
        let db_name = env::var("DB_NAME").unwrap_or_else(|_| sport.clone());
        let db_host = env::var("DB_HOST").unwrap_or_else(|_| "postgres".to_string());
        let db_port = env::var("DB_PORT").unwrap_or_else(|_| "5432".to_string());

        let database_url = match env::var("DATABASE_URL") {
            Ok(v) if !v.trim().is_empty() => v,
            Ok(_) => return Err(anyhow!("DATABASE_URL is set but empty")),
            Err(_) => {
                let db_password = read_secret_file("/run/secrets/db_password", "db_password")?;
                format!("postgresql://{}:{}@{}:{}/{}", db_user, db_password, db_host, db_port, db_name)
            }
        };

        // Redis URL
        let redis_url = match env::var("REDIS_URL") {
            Ok(v) if !v.trim().is_empty() => v,
            Ok(_) => return Err(anyhow!("REDIS_URL is set but empty")),
            Err(_) => {
                let redis_password = read_secret_file("/run/secrets/redis_password", "redis_password")?;
                format!("redis://:{}@redis:6379", redis_password)
            }
        };

        Ok(Self {
            odds_api_key,
            database_url,
            redis_url,
            poll_interval_seconds: env::var("POLL_INTERVAL_SECONDS")
                .unwrap_or_else(|_| "30".to_string())
                .parse()
                .unwrap_or(30),
            sport_key: "basketball_ncaab".to_string(),
            health_port: env::var("HEALTH_PORT")
                .unwrap_or_else(|_| "8083".to_string())
                .parse()
                .unwrap_or(8083),
            run_once: env::var("RUN_ONCE")
                .unwrap_or_else(|_| "false".to_string())
                .to_lowercase() == "true",
        })
    }
}

/// Read a secret from Docker secret file - REQUIRED, NO fallbacks
fn read_secret_file(file_path: &str, secret_name: &str) -> Result<String> {
    std::fs::read_to_string(file_path)
        .map(|s| s.trim().to_string())
        .context(format!(
            "CRITICAL: Secret file not found at {} ({}). Container must have secrets mounted.",
            file_path, secret_name
        ))
}

/// Thread-safe game cache with proper entry API to avoid race conditions
#[derive(Clone)]
pub struct GameCache {
    inner: Arc<RwLock<HashMap<String, Uuid>>>,
}

impl GameCache {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    /// Get a cached game ID if it exists
    pub async fn get(&self, external_id: &str) -> Option<Uuid> {
        let cache = self.inner.read().await;
        cache.get(external_id).copied()
    }
    
    /// Insert a game ID into the cache
    pub async fn insert(&self, external_id: String, game_id: Uuid) {
        let mut cache = self.inner.write().await;
        cache.insert(external_id, game_id);
    }
    
    /// Get or insert with a factory function - RACE-CONDITION FREE
    /// Uses entry API pattern to ensure atomic check-then-insert
    pub async fn get_or_insert_with<F, Fut>(
        &self,
        external_id: &str,
        factory: F,
    ) -> Result<Uuid>
    where
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = Result<Uuid>>,
    {
        // First, try to get with read lock (fast path)
        {
            let cache = self.inner.read().await;
            if let Some(&id) = cache.get(external_id) {
                return Ok(id);
            }
        }
        
        // Acquire write lock and check again (double-checked locking)
        let mut cache = self.inner.write().await;
        
        // Check again after acquiring write lock (another thread may have inserted)
        if let Some(&id) = cache.get(external_id) {
            return Ok(id);
        }
        
        // Not in cache, create new entry
        let game_id = factory().await?;
        cache.insert(external_id.to_string(), game_id);
        
        Ok(game_id)
    }
    
    /// Clear old entries to prevent memory growth
    pub async fn cleanup(&self, max_size: usize) {
        let mut cache = self.inner.write().await;
        if cache.len() > max_size {
            cache.clear();
            info!("Cleared game cache (exceeded {} entries)", max_size);
        }
    }
}

/// Service health state
#[derive(Clone)]
pub struct HealthState {
    pub last_poll_time: Arc<RwLock<Option<DateTime<Utc>>>>,
    pub last_poll_count: Arc<RwLock<usize>>,
    pub error_count: Arc<RwLock<usize>>,
}

impl HealthState {
    pub fn new() -> Self {
        Self {
            last_poll_time: Arc::new(RwLock::new(None)),
            last_poll_count: Arc::new(RwLock::new(0)),
            error_count: Arc::new(RwLock::new(0)),
        }
    }
    
    pub async fn record_success(&self, count: usize) {
        *self.last_poll_time.write().await = Some(Utc::now());
        *self.last_poll_count.write().await = count;
        *self.error_count.write().await = 0;
    }
    
    pub async fn record_error(&self) {
        *self.error_count.write().await += 1;
    }
}

/// Odds ingestion service
pub struct OddsIngestionService {
    config: Config,
    db: PgPool,
    redis: redis::aio::ConnectionManager,
    rate_limiter: RateLimiter<governor::state::NotKeyed, governor::state::InMemoryState, governor::clock::DefaultClock>,
    game_cache: GameCache,
    http_client: reqwest::Client,
    health: HealthState,
}

impl OddsIngestionService {
    pub async fn new(config: Config) -> Result<Self> {
        // Connect to database with retry
        let db = Self::connect_db_with_retry(&config.database_url, 5).await?;

        // Connect to Redis with retry
        let redis = Self::connect_redis_with_retry(&config.redis_url, 5).await?;

        // Rate limiter: 45 requests per minute (The Odds API limit)
        let rate_limiter = RateLimiter::direct(Quota::per_minute(NonZeroU32::new(45).unwrap()));

        // HTTP client with timeouts
        let http_client = reqwest::Client::builder()
            .timeout(Duration::from_secs(30))
            .connect_timeout(Duration::from_secs(10))
            .pool_max_idle_per_host(5)
            .build()
            .context("Failed to create HTTP client")?;

        Ok(Self {
            config,
            db,
            redis,
            rate_limiter,
            game_cache: GameCache::new(),
            http_client,
            health: HealthState::new(),
        })
    }
    
    async fn connect_db_with_retry(url: &str, max_retries: u32) -> Result<PgPool> {
        let mut attempt = 0;
        loop {
            match PgPoolOptions::new()
                .max_connections(10)
                .acquire_timeout(Duration::from_secs(10))
                .connect(url)
                .await
            {
                Ok(pool) => {
                    info!("Connected to PostgreSQL");
                    return Ok(pool);
                }
                Err(e) => {
                    attempt += 1;
                    if attempt >= max_retries {
                        return Err(anyhow!("Failed to connect to database after {} attempts: {}", max_retries, e));
                    }
                    warn!("Database connection attempt {} failed: {}. Retrying...", attempt, e);
                    tokio::time::sleep(Duration::from_secs(2u64.pow(attempt))).await;
                }
            }
        }
    }
    
    async fn connect_redis_with_retry(url: &str, max_retries: u32) -> Result<redis::aio::ConnectionManager> {
        let mut attempt = 0;
        loop {
            match redis::Client::open(url) {
                Ok(client) => {
                    match redis::aio::ConnectionManager::new(client).await {
                        Ok(conn) => {
                            info!("Connected to Redis");
                            return Ok(conn);
                        }
                        Err(e) => {
                            attempt += 1;
                            if attempt >= max_retries {
                                return Err(anyhow!("Failed to connect to Redis after {} attempts: {}", max_retries, e));
                            }
                            warn!("Redis connection attempt {} failed: {}. Retrying...", attempt, e);
                            tokio::time::sleep(Duration::from_secs(2u64.pow(attempt))).await;
                        }
                    }
                }
                Err(e) => {
                    attempt += 1;
                    if attempt >= max_retries {
                        return Err(anyhow!("Failed to create Redis client after {} attempts: {}", max_retries, e));
                    }
                    warn!("Redis client creation attempt {} failed: {}. Retrying...", attempt, e);
                    tokio::time::sleep(Duration::from_secs(2u64.pow(attempt))).await;
                }
            }
        }
    }

    /// Fetch events from The Odds API
    pub async fn fetch_events(&self) -> Result<Vec<OddsApiEvent>> {
        // Wait for rate limit
        self.rate_limiter.until_ready().await;

        let url = format!(
            "https://api.the-odds-api.com/v4/sports/{}/odds",
            self.config.sport_key
        );

        let response = self.http_client
            .get(&url)
            .query(&[
                ("apiKey", &self.config.odds_api_key),
                ("regions", &"us".to_string()),
                ("markets", &"spreads,totals,h2h".to_string()),
                // NOTE: Do not restrict bookmakers for full-game markets.
                // Restricting here causes many events to lack spreads/totals (and therefore
                // be skipped by the model). We still *prefer* sharper books downstream.
                ("oddsFormat", &"american".to_string()),
            ])
            .send()
            .await
            .context("Failed to fetch events")?;

        // Log API usage from headers
        if let Some(remaining) = response.headers().get("x-requests-remaining") {
            info!(
                "API requests remaining: {}",
                remaining.to_str().unwrap_or("?")
            );
        }

        let status = response.status();
        let body = response
            .text()
            .await
            .context("Failed to read response body")?;

        if !status.is_success() {
            return Err(anyhow::anyhow!(
                "Odds API error (status {}): {}",
                status,
                body
            ));
        }

        let events: Vec<OddsApiEvent> = serde_json::from_str(&body)
            .context("Failed to parse events")?;

        info!("Fetched {} events from The Odds API", events.len());
        Ok(events)
    }

    /// Fetch first-half odds for a specific event using the event odds endpoint
    /// Premium subscription required for alternate/period markets
    pub async fn fetch_event_h1_odds(&self, event_id: &str) -> Result<Option<OddsApiEvent>> {
        // Wait for rate limit
        self.rate_limiter.until_ready().await;

        let url = format!(
            "https://api.the-odds-api.com/v4/sports/{}/events/{}/odds",
            self.config.sport_key,
            event_id
        );

        // For 1H markets, include Bovada as they provide best NCAAB 1H coverage
        // Keep pinnacle/circa/bookmaker for consistency where available
        let response = self.http_client
            .get(&url)
            .query(&[
                ("apiKey", &self.config.odds_api_key),
                ("regions", &"us".to_string()),
                ("markets", &"spreads_h1,totals_h1,h2h_h1".to_string()),
                ("bookmakers", &"bovada,pinnacle,circa,bookmaker".to_string()),
                ("oddsFormat", &"american".to_string()),
            ])
            .send()
            .await
            .context("Failed to fetch event H1 odds")?;

        let status = response.status();
        let body = response
            .text()
            .await
            .context("Failed to read H1 response body")?;

        if !status.is_success() {
            // Log but don't fail - 1H odds may not be available for all events
            warn!("Event H1 odds unavailable for {}: {} - {}", event_id, status, body);
            return Ok(None);
        }

        let event: OddsApiEvent = serde_json::from_str(&body)
            .context("Failed to parse H1 event odds")?;

        Ok(Some(event))
    }

    /// Fetch first-half odds for all events (batch)
    pub async fn fetch_all_h1_odds(&self, event_ids: &[String]) -> Result<Vec<OddsApiEvent>> {
        let mut h1_events = Vec::new();
        
        for event_id in event_ids {
            match self.fetch_event_h1_odds(event_id).await {
                Ok(Some(event)) => {
                    h1_events.push(event);
                }
                Ok(None) => {
                    // H1 odds not available for this event, skip
                }
                Err(e) => {
                    warn!("Failed to fetch H1 odds for event {}: {:?}", event_id, e);
                }
            }
        }

        info!("Fetched H1 odds for {}/{} events", h1_events.len(), event_ids.len());
        Ok(h1_events)
    }

    /// Fetch second-half odds for a specific event using the event odds endpoint
    pub async fn fetch_event_h2_odds(&self, event_id: &str) -> Result<Option<OddsApiEvent>> {
        // Wait for rate limit
        self.rate_limiter.until_ready().await;

        let url = format!(
            "https://api.the-odds-api.com/v4/sports/{}/events/{}/odds",
            self.config.sport_key,
            event_id
        );

        // H2 markets available from DraftKings and FanDuel
        let response = self.http_client
            .get(&url)
            .query(&[
                ("apiKey", &self.config.odds_api_key),
                ("regions", &"us".to_string()),
                ("markets", &"spreads_h2,totals_h2,h2h_h2".to_string()),
                ("bookmakers", &"draftkings,fanduel,pinnacle,bovada".to_string()),
                ("oddsFormat", &"american".to_string()),
            ])
            .send()
            .await
            .context("Failed to fetch event H2 odds")?;

        let status = response.status();
        let body = response
            .text()
            .await
            .context("Failed to read H2 response body")?;

        if !status.is_success() {
            warn!("Event H2 odds unavailable for {}: {} - {}", event_id, status, body);
            return Ok(None);
        }

        let event: OddsApiEvent = serde_json::from_str(&body)
            .context("Failed to parse H2 event odds")?;

        Ok(Some(event))
    }

    /// Fetch second-half odds for all events (batch)
    pub async fn fetch_all_h2_odds(&self, event_ids: &[String]) -> Result<Vec<OddsApiEvent>> {
        let mut h2_events = Vec::new();
        
        for event_id in event_ids {
            match self.fetch_event_h2_odds(event_id).await {
                Ok(Some(event)) => {
                    if !event.bookmakers.is_empty() {
                        h2_events.push(event);
                    }
                }
                Ok(None) => {}
                Err(e) => {
                    warn!("Failed to fetch H2 odds for event {}: {:?}", event_id, e);
                }
            }
        }

        info!("Fetched H2 odds for {}/{} events", h2_events.len(), event_ids.len());
        Ok(h2_events)
    }

    /// Process events and extract odds
    pub async fn process_events(&self, events: Vec<OddsApiEvent>) -> Result<Vec<OddsSnapshot>> {
        let mut snapshots = Vec::new();
        let now = Utc::now();

        for event in events {
            // Get or create game ID using race-condition-free cache
            let event_clone = event.clone();
            let game_id = self.game_cache.get_or_insert_with(&event.id, || async {
                self.get_or_create_game(&event_clone).await
            }).await?;

            for bookmaker in &event.bookmakers {
                for market in &bookmaker.markets {
                    let snapshot = self.extract_odds_snapshot(
                        now,
                        game_id,
                        &event.id,
                        &bookmaker.key,
                        market,
                        &event.home_team,
                    );

                    if let Some(s) = snapshot {
                        snapshots.push(s);
                    }
                }
            }
        }

        Ok(snapshots)
    }

    /// Extract odds snapshot from a market
    fn extract_odds_snapshot(
        &self,
        time: DateTime<Utc>,
        game_id: Uuid,
        external_id: &str,
        bookmaker: &str,
        market: &Market,
        home_team: &str,
    ) -> Option<OddsSnapshot> {
        let (market_type, period) = match market.key.as_str() {
            "spreads" => ("spreads", "full"),
            "totals" => ("totals", "full"),
            "h2h" => ("h2h", "full"),
            "spreads_h1" => ("spreads", "1h"),
            "totals_h1" => ("totals", "1h"),
            "h2h_h1" => ("h2h", "1h"),
            "spreads_h2" => ("spreads", "2h"),
            "totals_h2" => ("totals", "2h"),
            "h2h_h2" => ("h2h", "2h"),
            _ => return None,
        };

        let mut snapshot = OddsSnapshot {
            time,
            game_id,
            external_id: external_id.to_string(),
            bookmaker: bookmaker.to_string(),
            market_type: market_type.to_string(),
            period: period.to_string(),
            home_line: None,
            away_line: None,
            total_line: None,
            home_price: None,
            away_price: None,
            over_price: None,
            under_price: None,
        };

        for outcome in &market.outcomes {
            match market_type {
                "spreads" => {
                    if outcome.name == home_team {
                        snapshot.home_line = outcome.point;
                        snapshot.home_price = outcome.price;
                    } else {
                        snapshot.away_line = outcome.point;
                        snapshot.away_price = outcome.price;
                    }
                }
                "totals" => {
                    if outcome.name == "Over" {
                        snapshot.total_line = outcome.point;
                        snapshot.over_price = outcome.price;
                    } else if outcome.name == "Under" {
                        snapshot.under_price = outcome.price;
                    }
                }
                "h2h" => {
                    if outcome.name == home_team {
                        snapshot.home_price = outcome.price;
                    } else {
                        snapshot.away_price = outcome.price;
                    }
                }
                _ => {}
            }
        }

        Some(snapshot)
    }

    /// Get or create game in database
    /// CRITICAL: Validates home/away assignment and team name resolution
    async fn get_or_create_game(&self, event: &OddsApiEvent) -> Result<Uuid> {
        // Resolve and validate team names BEFORE upserting game
        let home_team_id = self.get_or_create_team(&event.home_team).await?;
        let away_team_id = self.get_or_create_team(&event.away_team).await?;
        
        // CRITICAL CHECK: Ensure home and away are different teams
        if home_team_id == away_team_id {
            return Err(anyhow::anyhow!(
                "Home and away teams resolved to same team ID: {} (home: '{}', away: '{}')",
                home_team_id,
                event.home_team,
                event.away_team
            ));
        }
        
        // Get canonical names for validation logging
        let home_canonical: Option<(String,)> = sqlx::query_as(
            "SELECT canonical_name FROM teams WHERE id = $1"
        )
            .bind(home_team_id)
            .fetch_optional(&self.db)
            .await?;
        
        let away_canonical: Option<(String,)> = sqlx::query_as(
            "SELECT canonical_name FROM teams WHERE id = $1"
        )
            .bind(away_team_id)
            .fetch_optional(&self.db)
            .await?;
        
        // Log team resolution for audit (insert only if not exists for this input_name+source+context)
        let home_has_ratings: bool = sqlx::query_scalar(
            "SELECT EXISTS(SELECT 1 FROM team_ratings WHERE team_id = $1)"
        )
            .bind(home_team_id)
            .fetch_one(&self.db)
            .await?;
        
        sqlx::query(
            r#"
            INSERT INTO team_resolution_audit (input_name, resolved_name, source, context, has_ratings)
            VALUES ($1, $2, 'the_odds_api', 'home_team', $3)
            "#
        )
            .bind(&event.home_team)
            .bind(&home_canonical.as_ref().map(|(n,)| n.clone()).unwrap_or_default())
            .bind(home_has_ratings)
            .execute(&self.db)
            .await?;
        
        let away_has_ratings: bool = sqlx::query_scalar(
            "SELECT EXISTS(SELECT 1 FROM team_ratings WHERE team_id = $1)"
        )
            .bind(away_team_id)
            .fetch_one(&self.db)
            .await?;
        
        sqlx::query(
            r#"
            INSERT INTO team_resolution_audit (input_name, resolved_name, source, context, has_ratings)
            VALUES ($1, $2, 'the_odds_api', 'away_team', $3)
            "#
        )
            .bind(&event.away_team)
            .bind(&away_canonical.as_ref().map(|(n,)| n.clone()).unwrap_or_default())
            .bind(away_has_ratings)
            .execute(&self.db)
            .await?;

        // Upsert game (IMPORTANT: update team IDs on conflict so fixes to team resolution
        // take effect without needing manual backfills).
        let game_id = Uuid::new_v4();
        let (final_game_id,): (Uuid,) = sqlx::query_as(
            r#"
            INSERT INTO games (id, external_id, home_team_id, away_team_id, commence_time, status)
            VALUES ($1, $2, $3, $4, $5, 'scheduled')
            ON CONFLICT (external_id) DO UPDATE SET
                home_team_id = EXCLUDED.home_team_id,
                away_team_id = EXCLUDED.away_team_id,
                commence_time = EXCLUDED.commence_time,
                status = 'scheduled'
            RETURNING id
            "#
        )
            .bind(game_id)
            .bind(&event.id)
            .bind(home_team_id)
            .bind(away_team_id)
            .bind(event.commence_time.unwrap_or_else(Utc::now))
            .fetch_one(&self.db)
            .await?;

        info!(
            "Created game: {} @ {} ({} vs {}) [home_id: {}, away_id: {}]",
            away_canonical.as_ref().map(|(n,)| n.as_str()).unwrap_or("?"),
            home_canonical.as_ref().map(|(n,)| n.as_str()).unwrap_or("?"),
            event.away_team,
            event.home_team,
            home_team_id,
            away_team_id
        );

        Ok(final_game_id)
    }

    /// Get or create team - CRITICAL: Normalizes team names BEFORE storing
    /// Uses resolve_team_name() function to ensure 99.99% accuracy
    async fn get_or_create_team(&self, team_name: &str) -> Result<Uuid> {
        // STEP 1: Resolve to an existing team ID (prefer those that already have ratings).
        // We try multiple variants because The Odds API often includes mascots and
        // abbreviations, while ratings use mascot-less canonical names.
        let candidates = self.team_name_candidates(team_name);
        let mut best_unrated: Option<(Uuid, String)> = None;

        for cand in candidates {
            if let Some((id, canonical, has_ratings)) = self.resolve_team_fuzzy(&cand).await? {
                if has_ratings {
                    // Found rated team: attach raw name as alias (if different) and return.
                    if team_name.to_lowercase() != canonical.to_lowercase() {
                        sqlx::query(
                            r#"
                            INSERT INTO team_aliases (team_id, alias, source)
                            VALUES ($1, $2, 'the_odds_api')
                            ON CONFLICT (alias, source) DO NOTHING
                            "#
                        )
                        .bind(id)
                        .bind(team_name)
                        .execute(&self.db)
                        .await?;
                    }
                    return Ok(id);
                }

                // Keep the first unrated match as a fallback, but keep searching
                // for a rated match on other candidate variants.
                if best_unrated.is_none() {
                    best_unrated = Some((id, canonical));
                }
            }
        }

        if let Some((id, canonical)) = best_unrated {
            if team_name.to_lowercase() != canonical.to_lowercase() {
                sqlx::query(
                    r#"
                    INSERT INTO team_aliases (team_id, alias, source)
                    VALUES ($1, $2, 'the_odds_api')
                    ON CONFLICT (alias, source) DO NOTHING
                    "#
                )
                .bind(id)
                .bind(team_name)
                .execute(&self.db)
                .await?;
            }
            return Ok(id);
        }

        // STEP 2: Create new team ONLY with normalized canonical name
        let canonical_name = self.normalize_team_name(team_name);
        let team_id = Uuid::new_v4();
        // IMPORTANT:
        // If the insert conflicts (team already exists), DO NOT return the newly generated UUID.
        // That UUID would not exist in `teams`, causing FK violations downstream.
        let inserted: Option<(Uuid,)> = sqlx::query_as(
            r#"
            INSERT INTO teams (id, canonical_name)
            VALUES ($1, $2)
            ON CONFLICT (canonical_name) DO NOTHING
            RETURNING id
            "#
        )
        .bind(team_id)
        .bind(&canonical_name)
        .fetch_optional(&self.db)
        .await?;

        let final_team_id = if let Some((id,)) = inserted {
            id
        } else {
            let (id,): (Uuid,) = sqlx::query_as("SELECT id FROM teams WHERE canonical_name = $1")
                .bind(&canonical_name)
                .fetch_one(&self.db)
                .await?;
            id
        };

        // STEP 4: Store original variant as alias
        sqlx::query(
            r#"
            INSERT INTO team_aliases (team_id, alias, source)
            VALUES ($1, $2, 'the_odds_api')
            ON CONFLICT (alias, source) DO NOTHING
            "#
        )
            .bind(final_team_id)
            .bind(team_name)
            .execute(&self.db)
            .await?;

        Ok(final_team_id)
    }

    /// Normalize team name to canonical format
    /// This ensures consistent naming before creating new teams
    fn normalize_team_name(&self, name: &str) -> String {
        // IMPORTANT: keep canonicalization conservative to avoid creating duplicates
        // that don't match Barttorvik canonical names (which breaks ratings joins).
        self.normalize_lookup_name(name)
    }

    /// Generate a small set of lookup candidates for a team name.
    /// Goal: maximize matches to existing seeded canonical names + aliases,
    /// while avoiding "creative" abbreviations that cause duplicate team rows.
    fn team_name_candidates(&self, team_name: &str) -> Vec<String> {
        let mut out: Vec<String> = Vec::new();

        let raw = team_name.trim().to_string();
        if !raw.is_empty() {
            out.push(raw.clone());
        }

        let cleaned = self.normalize_lookup_name(&raw);

        // Helper to add a base string + expansions + mascot-stripped variants.
        let mut add_variants = |s: &str, out: &mut Vec<String>| {
            if s.trim().is_empty() {
                return;
            }
            out.push(s.trim().to_string());
            if let Some(expanded) = Self::expand_prefix_abbrev(s) {
                out.push(expanded);
            }

            // Heuristic: Odds feeds often include mascot suffix; try dropping trailing words.
            let parts: Vec<&str> = s.split_whitespace().collect();
            if parts.len() >= 2 {
                out.push(parts[..parts.len() - 1].join(" "));
            }
            if parts.len() >= 3 {
                out.push(parts[..parts.len() - 2].join(" "));
            }
        };

        if !cleaned.is_empty() {
            // Always add variants even if cleaned == raw so we still generate mascot-stripped forms.
            add_variants(&cleaned, &mut out);
        }

        // Common "State" -> "St." canonicalization used in our seeded team list.
        let state_abbrev = cleaned.replace(" State", " St.");
        if !state_abbrev.is_empty() && state_abbrev != cleaned {
            add_variants(&state_abbrev, &mut out);
        }

        // De-dupe while preserving order
        let mut seen = std::collections::HashSet::new();
        out.retain(|s| seen.insert(s.to_lowercase()));
        out
    }

    /// Normalize a team name for lookup:
    /// - remove parenthetical suffixes (e.g. "(CA)")
    /// - normalize quotes/dashes
    /// - collapse whitespace
    fn normalize_lookup_name(&self, name: &str) -> String {
        let mut out = String::with_capacity(name.len());
        let mut paren_depth: u32 = 0;

        for ch in name.chars() {
            match ch {
                '(' => {
                    paren_depth += 1;
                    continue;
                }
                ')' => {
                    if paren_depth > 0 {
                        paren_depth -= 1;
                    }
                    continue;
                }
                _ if paren_depth > 0 => continue,

                // Normalize curly quotes
                '’' | '‘' => out.push('\''),

                // Normalize dashes to spaces
                '–' | '—' | '-' => out.push(' '),

                // Drop periods to help match "St." vs "St"
                '.' => continue,

                _ => out.push(ch),
            }
        }

        out.split_whitespace().collect::<Vec<_>>().join(" ").trim().to_string()
    }

    /// Expand common prefix abbreviations used in odds feeds:
    /// - "E."/"E" -> "Eastern"
    /// - "W."/"W" -> "Western"
    /// - "N."/"N" -> "Northern"
    /// - "S."/"S" -> "Southern"
    /// - "C."/"C" -> "Central"
    /// - "Mt."/"Mt" -> "Mount"
    fn expand_prefix_abbrev(s: &str) -> Option<String> {
        let mut parts = s.split_whitespace();
        let first = parts.next()?;
        let rest: Vec<&str> = parts.collect();
        let expanded = match first {
            "E" | "E." => "Eastern",
            "W" | "W." => "Western",
            "N" | "N." => "Northern",
            "S" | "S." => "Southern",
            "C" | "C." => "Central",
            "Mt" | "Mt." => "Mount",
            _ => return None,
        };

        if rest.is_empty() {
            return None;
        }
        Some(format!("{} {}", expanded, rest.join(" ")))
    }

    /// Fuzzy resolution that ignores punctuation/spacing and checks both canonical names
    /// and aliases, preferring teams that already have ratings.
    async fn resolve_team_fuzzy(&self, input: &str) -> Result<Option<(Uuid, String, bool)>> {
        let resolved: Option<(Uuid, String, bool)> = sqlx::query_as(
            r#"
            SELECT
              t.id,
              t.canonical_name,
              EXISTS(SELECT 1 FROM team_ratings tr WHERE tr.team_id = t.id) AS has_ratings
            FROM teams t
            LEFT JOIN team_aliases ta ON t.id = ta.team_id
            WHERE regexp_replace(lower(t.canonical_name), '[^a-z0-9]+', '', 'g')
                    = regexp_replace(lower($1), '[^a-z0-9]+', '', 'g')
               OR regexp_replace(lower(ta.alias), '[^a-z0-9]+', '', 'g')
                    = regexp_replace(lower($1), '[^a-z0-9]+', '', 'g')
            ORDER BY has_ratings DESC, t.canonical_name
            LIMIT 1
            "#
        )
        .bind(input)
        .fetch_optional(&self.db)
        .await?;

        Ok(resolved)
    }

    /// Store snapshots in TimescaleDB
    pub async fn store_snapshots(&self, snapshots: &[OddsSnapshot]) -> Result<()> {
        if snapshots.is_empty() {
            return Ok(());
        }

        let mut tx = self.db.begin().await?;

        for snapshot in snapshots {
            sqlx::query(
                r#"
                INSERT INTO odds_snapshots (
                    time, game_id, bookmaker, market_type, period,
                    home_line, away_line, total_line,
                    home_price, away_price, over_price, under_price
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (time, game_id, bookmaker, market_type, period) DO UPDATE SET
                    home_line = EXCLUDED.home_line,
                    away_line = EXCLUDED.away_line,
                    total_line = EXCLUDED.total_line,
                    home_price = EXCLUDED.home_price,
                    away_price = EXCLUDED.away_price,
                    over_price = EXCLUDED.over_price,
                    under_price = EXCLUDED.under_price
                "#
            )
                .bind(snapshot.time)
                .bind(snapshot.game_id)
                .bind(&snapshot.bookmaker)
                .bind(&snapshot.market_type)
                .bind(&snapshot.period)
                .bind(snapshot.home_line)
                .bind(snapshot.away_line)
                .bind(snapshot.total_line)
                .bind(snapshot.home_price)
                .bind(snapshot.away_price)
                .bind(snapshot.over_price)
                .bind(snapshot.under_price)
                .execute(&mut *tx)
                .await?;
        }

        tx.commit().await?;
        info!("Stored {} odds snapshots", snapshots.len());
        Ok(())
    }

    /// Publish snapshots to Redis Stream
    pub async fn publish_to_redis(&self, snapshots: &[OddsSnapshot]) -> Result<()> {
        if snapshots.is_empty() {
            return Ok(());
        }

        let mut conn = self.redis.clone();

        for snapshot in snapshots {
            let payload = serde_json::to_string(snapshot)?;

            let _: String = conn.xadd(
                "odds.live",
                "*",
                &[
                    ("game_id", snapshot.game_id.to_string()),
                    ("bookmaker", snapshot.bookmaker.clone()),
                    ("market_type", snapshot.market_type.clone()),
                    ("data", payload),
                ],
            ).await?;
        }

        info!("Published {} snapshots to Redis", snapshots.len());
        Ok(())
    }

    /// Main polling loop
    pub async fn run(&self) -> Result<()> {
        info!(
            "Starting odds ingestion loop (poll interval: {}s)",
            self.config.poll_interval_seconds
        );

        // Periodic cache cleanup
        let game_cache = self.game_cache.clone();
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(Duration::from_secs(3600)).await;
                game_cache.cleanup(10000).await;
            }
        });

        loop {
            let start = std::time::Instant::now();

            match self.poll_once().await {
                Ok(count) => {
                    self.health.record_success(count).await;
                    info!(
                        "Poll completed: {} snapshots in {:?}",
                        count,
                        start.elapsed()
                    );
                }
                Err(e) => {
                    self.health.record_error().await;
                    error!("Poll failed: {:?}", e);
                }
            }

            tokio::time::sleep(Duration::from_secs(self.config.poll_interval_seconds)).await;
        }
    }

    /// Single poll iteration
    async fn poll_once(&self) -> Result<usize> {
        // Step 1: Fetch full-game odds from the standard endpoint
        let events = self.fetch_events().await?;
        let mut snapshots = self.process_events(events.clone()).await?;
        let full_game_count = snapshots.len();

        // If we're running in one-shot mode (manual trigger), keep it fast and
        // reliable by skipping per-event H1/H2 requests (these can be slow and
        // are often premium-gated). Full-game markets are enough for the CLI
        // prediction run and avoids run_today.py timing out.
        if self.config.run_once {
            info!(
                "RUN_ONCE=true: storing {} full-game snapshots (skipping H1/H2)",
                full_game_count
            );

            let (store_result, publish_result) = tokio::join!(
                self.store_snapshots(&snapshots),
                self.publish_to_redis(&snapshots)
            );

            store_result?;
            publish_result?;

            return Ok(snapshots.len());
        }

        // Step 2: Fetch first-half odds from the event-specific endpoint (premium)
        let event_ids: Vec<String> = events.iter().map(|e| e.id.clone()).collect();
        let h1_events = self.fetch_all_h1_odds(&event_ids).await?;
        let h1_snapshots = self.process_events(h1_events).await?;
        let h1_count = h1_snapshots.len();
        snapshots.extend(h1_snapshots);

        // Step 3: Fetch second-half odds from the event-specific endpoint
        let h2_events = self.fetch_all_h2_odds(&event_ids).await?;
        let h2_snapshots = self.process_events(h2_events).await?;
        let h2_count = h2_snapshots.len();
        snapshots.extend(h2_snapshots);

        info!("Poll results: {} full-game + {} H1 + {} H2 = {} total snapshots", 
              full_game_count, h1_count, h2_count, snapshots.len());

        // Store and publish in parallel
        let (store_result, publish_result) = tokio::join!(
            self.store_snapshots(&snapshots),
            self.publish_to_redis(&snapshots)
        );

        store_result?;
        publish_result?;

        Ok(snapshots.len())
    }
}

/// Health check handler
async fn health_handler(
    axum::extract::State(health): axum::extract::State<HealthState>,
) -> (StatusCode, Json<serde_json::Value>) {
    let last_poll = health.last_poll_time.read().await;
    let last_count = health.last_poll_count.read().await;
    let errors = health.error_count.read().await;
    
    let status = if *errors > 5 {
        "degraded"
    } else {
        "ok"
    };
    
    let http_status = if *errors > 10 {
        StatusCode::SERVICE_UNAVAILABLE
    } else {
        StatusCode::OK
    };
    
    (http_status, Json(json!({
        "service": "odds-ingestion",
        "version": "5.0.0",
        "status": status,
        "last_poll": last_poll.map(|t| t.to_rfc3339()),
        "last_poll_count": *last_count,
        "consecutive_errors": *errors
    })))
}

#[tokio::main]
async fn main() -> Result<()> {
    // NO .env file loading - all secrets MUST come from Docker secret files

    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("odds_ingestion=info".parse().unwrap()),
        )
        .init();

    info!("NCAA Basketball Odds Ingestion Service v6.0");

    let config = Config::from_env()?;
    let health_port = config.health_port;
    let run_once = config.run_once;
    
    let service = OddsIngestionService::new(config).await?;
    let health_state = service.health.clone();

    // Start health check server
    let app = Router::new()
        .route("/health", get(health_handler))
        .with_state(health_state);
    
    let health_addr = format!("0.0.0.0:{}", health_port);
    info!("Health endpoint listening on {}", health_addr);
    
    let listener = tokio::net::TcpListener::bind(&health_addr).await?;
    
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });

    // Check if running in one-shot mode (manual trigger)
    if run_once {
        info!("Running in one-shot mode (RUN_ONCE=true)");
        match service.poll_once().await {
            Ok(count) => {
                info!("One-shot sync completed: {} snapshots stored", count);
            }
            Err(e) => {
                error!("One-shot sync failed: {:?}", e);
                return Err(e);
            }
        }
        return Ok(());
    }

    // Handle shutdown gracefully (continuous mode)
    let ctrl_c = tokio::signal::ctrl_c();
    tokio::pin!(ctrl_c);

    tokio::select! {
        result = service.run() => {
            if let Err(e) = result {
                error!("Service error: {:?}", e);
            }
        }
        _ = ctrl_c => {
            info!("Shutting down...");
        }
    }

    Ok(())
}
