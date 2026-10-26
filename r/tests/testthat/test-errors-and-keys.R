test_that("a missing key is friendly and makes no request", {
  local_aq()
  calls <- 0L
  httr2::with_mocked_responses(function(req) { calls <<- calls + 1L; ok_echo(req) }, {
    e <- expect_error(strata("MARIA", "GARCIA"), class = "aq_error_auth")
    expect_match(conditionMessage(e), "aq_set_key")
    expect_match(conditionMessage(e), "AEQUUM_API_KEY")
    expect_match(conditionMessage(e), "Email terry@aequum.ai")
  })
  expect_equal(calls, 0L)
})

test_that("401, 429, 422 are friendly", {
  local_aq(); aq_set_key(SENTINEL)
  httr2::with_mocked_responses(function(req) err_resp(401L, "invalid_api_key"), {
    expect_error(strata("MARIA", "GARCIA"), "didn't accept your key \\(HTTP 401\\)", class = "aq_error_auth")
  })
  n <- 0L
  httr2::with_mocked_responses(function(req) { n <<- n + 1L; err_resp(429L, "quota_exceeded") }, {
    expect_error(strata("MARIA", "GARCIA"), "today's free limit \\(HTTP 429\\)", class = "aq_error_quota")
  })
  expect_equal(n, 1L)                      # the daily limit is not retried
  httr2::with_mocked_responses(function(req) err_resp(422L, "bad_request", "1 of 1 records lack the geography"), {
    expect_error(strata("MARIA", "GARCIA"), "couldn't read the input \\(HTTP 422\\)", class = "aq_error_input")
  })
})

test_that("a transient rate limit is retried", {
  local_aq(); aq_set_key(SENTINEL)
  n <- 0L
  httr2::with_mocked_responses(function(req) {
    n <<- n + 1L
    if (n < 2L) err_resp(429L, "rate_limited", headers = list(`Retry-After` = "0")) else ok_echo(req)
  }, {
    out <- strata("MARIA", "GARCIA")
    expect_equal(nrow(out), 1L)
  })
  expect_equal(n, 2L)
})

test_that("503 warm-up waits and retries, then gives up politely", {
  local_aq(); aq_set_key(SENTINEL)
  n <- 0L
  httr2::with_mocked_responses(function(req) {
    n <<- n + 1L
    if (n <= 4L) err_resp(503L, "backend_unavailable") else ok_echo(req)
  }, {
    expect_message(out <- strata("MARIA", "GARCIA"), "starting up")
    expect_equal(nrow(out), 1L)
  })
  expect_equal(n, 5L)
  options(aqEthnicity.warmup_retries = 2L)
  httr2::with_mocked_responses(function(req) err_resp(503L, "backend_unavailable"), {
    suppressMessages(expect_error(strata("MARIA", "GARCIA"), "still starting up \\(HTTP 503\\)",
                                  class = "aq_error_unavailable"))
  })
})

test_that("the key is sent but never printed, formatted or put in an error", {
  local_aq()
  seen <- NULL
  expect_silent(aq_set_key(SENTINEL))
  out <- capture.output(msgs <- testthat::capture_messages(
    httr2::with_mocked_responses(function(req) { seen <<- req; ok_echo(req) }, strata("MARIA", "GARCIA"))))
  expect_true(any(grepl(SENTINEL, unlist(httr2::req_get_headers(seen, redacted = "reveal")), fixed = TRUE)))   # it IS in the request
  printed <- c(out, msgs,
               capture.output(print(seen)),                                # httr2 redacts Authorization
               capture.output(print(aqEthnicity:::.aq_state$key)),
               format(aqEthnicity:::.aq_state$key), as.character(aqEthnicity:::.aq_state$key),
               toString(aqEthnicity:::.aq_state$key), capture.output(str(as.list(aqEthnicity:::.aq_state))))
  expect_false(any(grepl(SENTINEL, printed, fixed = TRUE)))

  for (st in list(list(401L, "invalid_api_key"), list(429L, "quota_exceeded"), list(422L, "bad_request"),
                  list(500L, "internal"))) {
    options(aqEthnicity.warmup_retries = 0L)
    e <- httr2::with_mocked_responses(function(req) err_resp(st[[1]], st[[2]]),
                                      tryCatch(strata("MARIA", "GARCIA"), error = function(e) e))
    blob <- paste(conditionMessage(e), paste(capture.output(print(e)), collapse = " "))
    expect_false(grepl(SENTINEL, blob, fixed = TRUE))
  }
  e <- httr2::with_mocked_responses(function(req) stop("boom ", SENTINEL),
                                    tryCatch(strata("MARIA", "GARCIA"), error = function(e) e))
  expect_false(grepl(SENTINEL, conditionMessage(e), fixed = TRUE))       # a hostile network error is not echoed
  expect_s3_class(e, "aq_error_unavailable")
})

test_that("the key comes from the environment too, and an empty key is refused", {
  local_aq()
  Sys.setenv(AEQUUM_API_KEY = SENTINEL)
  on.exit(Sys.unsetenv("AEQUUM_API_KEY"), add = TRUE)
  auth <- NULL
  httr2::with_mocked_responses(function(req) { auth <<- httr2::req_get_headers(req, redacted = "reveal")$Authorization; ok_echo(req) },
                               strata("MARIA", "GARCIA"))
  expect_equal(as.character(auth), paste("Bearer", SENTINEL))
  expect_error(aq_set_key("  "), class = "aq_error_auth")
})
