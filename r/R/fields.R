# Field names the service understands, and the spellings it would silently ignore ----------------

.aq_fields <- c("first_name", "middle_name", "last_name", "zcta", "tract", "block_group",
                "address", "city", "state", "zip5")
.aq_aliases <- c(fname = "first_name", mname = "middle_name", lname = "last_name",
                 first = "first_name", middle = "middle_name", last = "last_name",
                 firstname = "first_name", middlename = "middle_name", lastname = "last_name",
                 surname = "last_name", given_name = "first_name", zip = "zip5", zipcode = "zip5",
                 zip_code = "zip5", postal_code = "zip5", bg = "block_group",
                 blockgroup = "block_group", census_tract = "tract", street = "address",
                 street_address = "address")

.aq_unknown_message <- function(name, where) {
  hint <- unname(.aq_aliases[tolower(name)])
  tail <- if (!is.na(hint)) {
    sprintf(" Did you mean '%s'?", hint)
  } else {
    paste0(" Accepted fields: ", paste(sort(.aq_fields), collapse = ", "), ".")
  }
  sprintf(paste0("unknown field '%s' in %s. The service would ignore it and score without that ",
                 "data, so it is refused here.%s"), name, where, tail)
}

# Refuse unexpected named arguments (e.g. mname = ...) before anything is sent.
.aq_reject_unknown <- function(dots, fn) {
  if (length(dots) == 0L) return(invisible(NULL))
  nm <- names(dots)
  bad <- if (is.null(nm) || !nzchar(nm[1L])) "<unnamed argument>" else nm[1L]
  .aq_abort(.aq_unknown_message(bad, paste0(fn, "()")), "aq_error_field")
}

# Passthrough columns are the caller's own, but a name the service reads as a field would be
# consumed as data rather than echoed back.
.aq_check_passthrough <- function(passthrough) {
  if (is.null(passthrough)) return(invisible(NULL))
  if (!is.list(passthrough) || is.null(names(passthrough)) || any(!nzchar(names(passthrough)))) {
    .aq_abort("passthrough must be a named list of vectors.", "aq_error_input")
  }
  for (k in names(passthrough)) {
    if (tolower(k) %in% names(.aq_aliases) || k %in% .aq_fields) {
      .aq_abort(paste0(.aq_unknown_message(k, "passthrough"),
                       " Passthrough names must not collide with field names."), "aq_error_field")
    }
  }
  invisible(NULL)
}

# Named arguments -> equal-length character columns. NULL is dropped; a length-one value recycles
# (a scalar is a promise that it applies to every row); other length mismatches are an error.
.aq_columns <- function(...) {
  args <- list(...)
  args <- args[!vapply(args, is.null, logical(1))]
  if (length(args) == 0L) .aq_abort("no input columns supplied.", "aq_error_input")
  len <- vapply(args, length, integer(1))
  n <- max(len)
  bad <- len != n & len != 1L
  if (any(bad)) {
    .aq_abort(sprintf("length mismatch: %s but the longest is %d. Pass vectors of the same length (a single value repeats).",
                      paste0(names(len)[bad], "=", len[bad], collapse = ", "), n), "aq_error_input")
  }
  if (n == 0L) .aq_abort("no input records supplied.", "aq_error_input")
  lapply(args, function(v) {
    v <- if (is.factor(v)) as.character(v) else v
    v <- as.character(v)
    if (length(v) == 1L && n > 1L) rep(v, n) else v
  })
}
