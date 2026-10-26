test_that("unknown fields such as mname are refused before any request", {
  local_aq(); aq_set_key(SENTINEL)
  calls <- 0L
  httr2::with_mocked_responses(function(req) { calls <<- calls + 1L; ok_echo(req) }, {
    e <- expect_error(strata("A", "B", mname = "C"), class = "aq_error_field")
    expect_match(conditionMessage(e), "mname")
    expect_match(conditionMessage(e), "middle_name")
    for (f in list(function() bisg("X", zcta = "11201", fname = "Y"),
                   function() bifsg("X", "Y", zcta = "11201", zipcode = "1"),
                   function() geocode("1 Main St", lname = "Z"),
                   function() predict_race_aq(data.frame(surname = "S"), mname = "Z"))) {
      expect_error(f(), class = "aq_error_field")
    }
    expect_error(strata("A", "B", passthrough = list(mname = "C")), class = "aq_error_field")
  })
  expect_equal(calls, 0L)
})

test_that("middle_name is the accepted spelling and passthrough echoes", {
  local_aq(); aq_set_key(SENTINEL)
  seen <- NULL
  httr2::with_mocked_responses(function(req) { seen <<- req$body$data; ok_echo(req, function(r) list(row = unlist(r$loan_id))) }, {
    out <- strata(c("MARIA", "JAMES"), c("GARCIA", "SMITH"), middle_name = c("L", "J"),
                  passthrough = list(loan_id = c("L1", "L2")))
    expect_equal(out$row, c("L1", "L2"))
  })
  expect_equal(unlist(seen$records$middle_name), c("L", "J"))
  expect_null(seen$records$mname)
  expect_equal(unlist(seen$options$passthrough), "loan_id")
})

test_that("the service address is a package default, overridable only by AEQUUM_BASE_URL", {
  local_aq(); aq_set_key(SENTINEL)
  expect_equal(aqEthnicity:::.aq_base_url(), "https://api.aequum.ai")
  url <- NULL
  httr2::with_mocked_responses(function(req) { url <<- req$url; ok_echo(req) }, strata("A", "B"))
  expect_equal(url, "https://api.aequum.ai/v1/strata/auto")
  Sys.setenv(AEQUUM_BASE_URL = "http://127.0.0.1:18088/")
  on.exit(Sys.unsetenv("AEQUUM_BASE_URL"), add = TRUE)
  expect_equal(aqEthnicity:::.aq_base_url(), "http://127.0.0.1:18088")
  expect_false("base_url" %in% names(formals(strata)))           # no URL argument anywhere
  expect_false("base_url" %in% names(formals(aq_set_key)))
})

test_that("large batches are split, stay aligned, and a wrong height is refused", {
  local_aq(); aq_set_key(SENTINEL)
  sizes <- integer()
  n <- 2500L
  httr2::with_mocked_responses(function(req) {
    sizes <<- c(sizes, length(req$body$data$records$last_name))
    ok_echo(req, function(r) list(echo = unlist(r$last_name)))
  }, {
    out <- strata(paste0("F", seq_len(n)), paste0("L", seq_len(n)))
  })
  expect_equal(nrow(out), n)
  expect_equal(sizes, c(1000L, 1000L, 500L))
  expect_equal(out$echo, paste0("L", seq_len(n)))                 # row for row, in order
  httr2::with_mocked_responses(function(req) json_resp(list(columns = list(p_white = rep(0.5, 999)))), {
    expect_error(strata(rep("A", 1000), rep("B", 1000)), "misaligned", class = "aq_error_misaligned")
  })
})

test_that("a forced-tier shortfall is restated in the caller's row numbers", {
  local_aq(); aq_set_key(SENTINEL)
  httr2::with_mocked_responses(function(req) {
    if (length(req$body$data$records$last_name) == 1000L) return(ok_echo(req))
    err_resp(422L, "bad_request", "lack the geography",
             details = list(shortfall_rows = list(3L), tier = "bgt"))
  }, {
    expect_error(strata(rep("A", 1500), rep("B", 1500), tier = "bgt"), "rows 1004 of your input",
                 class = "aq_error_input")
  })
})

test_that("length mismatches are errors, a single value recycles", {
  local_aq(); aq_set_key(SENTINEL)
  httr2::with_mocked_responses(function(req) ok_echo(req), {
    expect_equal(nrow(strata("MARIA", c("A", "B", "C"))), 3L)
    expect_error(strata(c("A", "B"), c("A", "B", "C")), "length mismatch", class = "aq_error_input")
  })
})

test_that("predict_race_aq returns the data frame with wru-style columns, in order", {
  local_aq(); aq_set_key(SENTINEL)
  df <- data.frame(surname = c("GARCIA", "SMITH", "CHEN"), first = c("MARIA", "JAMES", "WEI"),
                   zip = c("11201", "60601", "94110"), keep = 1:3)
  httr2::with_mocked_responses(function(req) ok_echo(req, function(r) list(iu = rep(0.1, length(r$last_name)),
                                                                           lookup_level = rep("ZIP", length(r$last_name)))), {
    out <- predict_race_aq(df, zip = "zip")
  })
  expect_equal(names(out), c(names(df), "pred.whi", "pred.bla", "pred.his", "pred.asi", "pred.oth",
                             "pred.iu", "pred.level"))
  expect_equal(out$keep, 1:3)
  expect_equal(out$pred.whi, rep(0.5, 3))
  expect_error(predict_race_aq(df, surname = "nope"), "not found in voter.file", class = "aq_error_input")
})

test_that("the request body is wire-correct: options is an object, one-record columns are arrays", {
  local_aq(); aq_set_key(SENTINEL)
  wire <- NULL
  httr2::with_mocked_responses(function(req) {
    wire <<- as.character(jsonlite::toJSON(req$body$data, auto_unbox = TRUE, null = "null", na = "null"))
    ok_echo(req)
  }, strata("MARIA", "GARCIA"))
  expect_match(wire, '"options":{}', fixed = TRUE)                 # not "options":[]
  expect_match(wire, '"last_name":["GARCIA"]', fixed = TRUE)       # a one-record column stays an array
  expect_false(grepl(SENTINEL, wire, fixed = TRUE))
})
