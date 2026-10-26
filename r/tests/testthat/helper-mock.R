# assembled at runtime so the repository secret scan never sees a key-shaped literal
SENTINEL <- paste0("aq_", "test_", "SENTINEL0123456789abcdef0123456789abcdef")

# Reset package state, make waits instant, and restore everything when the test ends.
local_aq <- function(.env = parent.frame()) {
  withr::local_options(aqEthnicity.warmup_wait = 0, aqEthnicity.max_retries = 1L,
                       aqEthnicity.warmup_retries = 12L, .local_envir = .env)
  withr::local_envvar(AEQUUM_API_KEY = NA, AEQUUM_BASE_URL = NA, .local_envir = .env)
  st <- aqEthnicity:::.aq_state
  if (exists("key", envir = st, inherits = FALSE)) rm("key", envir = st)
  invisible(NULL)
}

json_resp <- function(body, status = 200L, headers = list()) {
  httr2::response(status_code = status,
                  headers = c(list(`Content-Type` = "application/json"), headers),
                  body = charToRaw(jsonlite::toJSON(body, auto_unbox = TRUE, null = "null", na = "null")))
}

err_resp <- function(status, code, message = "x", details = NULL, headers = list()) {
  e <- list(code = code, message = message)
  if (!is.null(details)) e$details <- details
  json_resp(list(error = e), status, headers)
}

# An "echo" service: one row of probabilities per submitted record.
ok_echo <- function(req, extra = NULL) {
  recs <- req$body$data$records
  n <- length(recs[[1L]])
  cols <- list(p_white = rep(0.5, n), p_black = rep(0.2, n), p_hispanic = rep(0.2, n),
               p_asian = rep(0.05, n), p_other = rep(0.05, n))
  if (!is.null(extra)) cols <- c(cols, extra(recs))
  json_resp(list(columns = cols, meta = list(n_records = n)))
}
