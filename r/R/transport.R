# HTTP transport: friendly errors, 503 warm-up retry, batching ------------------------------------

.aq_opt <- function(name, default) getOption(paste0("aqEthnicity.", name), default)

.aq_friendly <- function(status, code, server_message) {
  if (status == 401L || identical(code, "invalid_api_key") || identical(code, "missing_api_key")) {
    return(paste("the API didn't accept your key (HTTP 401). Check it was pasted in full, with no",
                 "extra spaces.", .aq_key_help))
  }
  if (status == 429L) {
    if (identical(code, "rate_limited")) {
      return("too many requests too quickly (HTTP 429). Slow down and try again in a moment.")
    }
    return(paste("you've reached today's free limit (HTTP 429). It resets tomorrow; email",
                 "terry@aequum.ai if you need more."))
  }
  if (status == 422L) {
    return(paste0("the API couldn't read the input (HTTP 422): ", substr(server_message, 1L, 300L)))
  }
  if (status == 503L) {
    return(paste("the service is still starting up (HTTP 503). After a restart the address routes can",
                 "take about five minutes to load; try again shortly."))
  }
  server_message
}

.aq_class_for <- function(status, code) {
  if (status == 401L) return("aq_error_auth")
  if (status == 429L) return(if (identical(code, "rate_limited")) "aq_error_rate" else "aq_error_quota")
  if (status == 422L || status == 400L) return("aq_error_input")
  if (status == 503L) return("aq_error_unavailable")
  "aq_error_http"
}

.aq_json <- function(resp) {
  txt <- tryCatch(httr2::resp_body_string(resp), error = function(e) "")
  tryCatch(jsonlite::fromJSON(txt, simplifyVector = TRUE, simplifyDataFrame = FALSE,
                              simplifyMatrix = FALSE),
           error = function(e) NULL)
}

.aq_raise <- function(resp) {
  status <- httr2::resp_status(resp)
  payload <- .aq_json(resp)
  err <- if (is.list(payload) && is.list(payload$error)) payload$error else list()
  code <- err$code
  msg <- err$message
  if (is.null(msg) || !nzchar(msg)) {
    body <- tryCatch(httr2::resp_body_string(resp), error = function(e) "")
    msg <- if (grepl("<html|<!doctype", substr(tolower(body), 1L, 400L))) {
      sprintf("HTTP %d from the gateway rather than the API.", status)
    } else if (nzchar(body)) substr(body, 1L, 300L) else sprintf("HTTP %d", status)
  }
  .aq_abort(.aq_friendly(status, code, msg), .aq_class_for(status, code),
            status = status, code = code, details = err$details)
}

# One request, with retries. Returns the parsed JSON.
.aq_request <- function(method, path, body = NULL, needs_key = TRUE) {
  key <- if (needs_key) .aq_get_key() else NULL     # errors before any network call when no key
  req <- httr2::request(paste0(.aq_base_url(), path))
  req <- httr2::req_method(req, method)
  req <- httr2::req_user_agent(req, paste0("aqEthnicity-R/", utils::packageVersion("aqEthnicity")))
  req <- httr2::req_timeout(req, 300)
  req <- httr2::req_error(req, is_error = function(resp) FALSE)   # we map statuses ourselves
  if (!is.null(key)) {
    req <- httr2::req_headers(req, Authorization = paste("Bearer", key$reveal()), .redact = "Authorization")
  }
  if (!is.null(body)) req <- httr2::req_body_json(req, body, auto_unbox = TRUE, na = "null")

  max_retries <- .aq_opt("max_retries", 3L)
  warmups <- .aq_opt("warmup_retries", 12L)
  wait <- .aq_opt("warmup_wait", 30)
  attempt <- 0L
  warm <- 0L
  repeat {
    resp <- tryCatch(httr2::req_perform(req), error = function(e) e)
    if (inherits(resp, "error")) {
      if (attempt < max_retries) {
        Sys.sleep(min(2^attempt * 0.25, 4)); attempt <- attempt + 1L; next
      }
      .aq_abort(paste0("could not reach the service (", class(resp)[1L], "). Check your network ",
                       "connection and try again."), "aq_error_unavailable")
    }
    status <- httr2::resp_status(resp)
    if (status < 300L) return(.aq_json(resp))
    if (status == 503L && warm < warmups) {
      if (warm == 0L) {
        message("aqEthnicity: the service is starting up (HTTP 503); waiting and retrying (this can ",
                "take a few minutes after a restart)...")
      }
      warm <- warm + 1L; Sys.sleep(wait); next
    }
    if (status %in% c(500L, 502L, 504L) && attempt < max_retries) {
      Sys.sleep(min(2^attempt * 0.25, 4)); attempt <- attempt + 1L; next
    }
    if (status == 429L) {
      payload <- .aq_json(resp)
      code <- if (is.list(payload) && is.list(payload$error)) payload$error$code else NULL
      if (identical(code, "rate_limited") && attempt < max_retries) {
        ra <- suppressWarnings(as.numeric(httr2::resp_header(resp, "retry-after", default = "1")))
        Sys.sleep(if (is.na(ra)) 1 else min(ra, 10)); attempt <- attempt + 1L; next
      }
    }
    .aq_raise(resp)
  }
}

# POST columns to a route in chunks and stitch the answers back in input order.
.aq_predict <- function(path, columns, options = list(), chunksize = 1000L) {
  n <- length(columns[[1L]])
  chunksize <- as.integer(chunksize)
  if (is.na(chunksize) || chunksize < 1L) .aq_abort("chunksize must be a positive integer.", "aq_error_input")
  if (length(options) == 0L) options <- stats::setNames(list(), character(0))   # serialise as {} (an empty list would be [])
  parts <- list()
  for (start in seq(1L, n, by = chunksize)) {
    stop_ <- min(start + chunksize - 1L, n)
    idx <- start:stop_
    body <- list(records = lapply(columns, function(v) as.list(v[idx])), options = options)
    payload <- tryCatch(.aq_request("POST", path, body = body), aq_error_input = function(e) {
      rows <- e$details$shortfall_rows
      if (length(rows)) {
        shifted <- as.integer(rows) + (start - 1L) + 1L      # the caller's 1-based row numbers
        shown <- utils::head(shifted, 10L)
        e$message <- sprintf(
          paste0("the API couldn't read the input (HTTP 422): %d of %d submitted records lack the ",
                 "geography for the %s tier (rows %s%s of your input). Use strata() for the waterfall."),
          length(shifted), n, if (is.null(e$details$tier)) "requested" else e$details$tier,
          paste(shown, collapse = ", "), if (length(shifted) > 10L) ", ..." else "")
      }
      stop(e)
    })
    got <- payload$columns
    heights <- unique(vapply(got, length, integer(1)))
    if (length(got) && !identical(as.integer(heights), length(idx))) {
      .aq_abort(sprintf(paste0("the service returned %s rows for %d submitted records; refusing to ",
                               "return misaligned results. Retry with a smaller chunksize and report ",
                               "this if it persists."), paste(heights, collapse = "/"), length(idx)),
                "aq_error_misaligned")
    }
    parts[[length(parts) + 1L]] <- as.data.frame(got, stringsAsFactors = FALSE, optional = TRUE)
  }
  out <- do.call(rbind, parts)
  rownames(out) <- NULL
  out
}
