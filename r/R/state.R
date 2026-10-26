# Package state, the API key holder and the service address -----------------------------------

.aq_state <- new.env(parent = emptyenv())
.aq_default_url <- "https://api.aequum.ai"
.aq_key_help <- "No key yet? Email terry@aequum.ai for a free one."

# The service address is a package default; the only override is AEQUUM_BASE_URL (for testing).
.aq_base_url <- function() {
  u <- Sys.getenv("AEQUUM_BASE_URL", unset = "")
  if (nzchar(u)) sub("/+$", "", u) else .aq_default_url
}

# A key holder that cannot leak through print/format/as.character/toString.
.aq_secret <- function(x) {
  force(x)
  structure(list(reveal = function() x), class = "aq_secret")
}

#' @export
print.aq_secret <- function(x, ...) {
  cat("<aqEthnicity API key: hidden>\n")
  invisible(x)
}

#' @export
format.aq_secret <- function(x, ...) "<aqEthnicity API key: hidden>"

#' @export
as.character.aq_secret <- function(x, ...) "<aqEthnicity API key: hidden>"

#' @export
toString.aq_secret <- function(x, ...) "<aqEthnicity API key: hidden>"

#' Set the API key for this R session
#'
#' The key is kept in memory for the session and is never printed, logged or written to disk.
#' If \code{key} is \code{NULL}, an interactive session is asked for it with a masked prompt
#' (package \pkg{askpass}). Without a call to this function the key is read from the
#' \code{AEQUUM_API_KEY} environment variable.
#'
#' @param key A single character string, or \code{NULL} to be prompted.
#' @return \code{NULL}, invisibly.
#' @examples
#' \dontrun{
#' aq_set_key()            # masked prompt
#' aq_set_key("...")       # or pass it directly (avoid typing it into a script)
#' }
#' @export
aq_set_key <- function(key = NULL) {
  if (is.null(key)) key <- .aq_prompt_key()
  if (!is.character(key) || length(key) != 1L || is.na(key) || !nzchar(trimws(key))) {
    .aq_abort("aq_set_key() needs a single non-empty key string.", "aq_error_auth")
  }
  .aq_state$key <- .aq_secret(trimws(key))
  invisible(NULL)
}

.aq_prompt_key <- function() {
  if (interactive() && requireNamespace("askpass", quietly = TRUE)) {
    k <- askpass::askpass("aqEthnicity API key (input hidden): ")
    if (!is.null(k) && nzchar(k)) return(k)
  }
  .aq_abort(paste("no API key is set. Call aq_set_key() in an interactive session, or set the",
                  "AEQUUM_API_KEY environment variable.", .aq_key_help), "aq_error_auth")
}

# The key for a request: session key, then AEQUUM_API_KEY, then (interactive only) a masked prompt.
.aq_get_key <- function() {
  if (!is.null(.aq_state$key)) return(.aq_state$key)
  k <- trimws(Sys.getenv("AEQUUM_API_KEY", unset = ""))
  if (nzchar(k)) return(.aq_secret(k))
  if (interactive() && requireNamespace("askpass", quietly = TRUE)) {
    aq_set_key(NULL)
    return(.aq_state$key)
  }
  .aq_abort(paste("no API key is set. Call aq_set_key() or set the AEQUUM_API_KEY environment",
                  "variable.", .aq_key_help), "aq_error_auth")
}

# Typed, friendly conditions ---------------------------------------------------------------------

.aq_abort <- function(message, class, ..., call = NULL) {
  stop(structure(class = c(class, "aq_error", "error", "condition"),
                 list(message = message, call = call, ...)))
}
