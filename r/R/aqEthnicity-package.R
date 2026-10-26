#' aqEthnicity: hosted race and ethnicity probabilities
#'
#' A client for the hosted aqEthnicity service: BISG, BIFSG, the STRATA name-and-address model and
#' address geocoding, with a \pkg{wru}-style wrapper. Outputs are statistical estimates for groups
#' of people, not statements about any individual. The service address is built in (the only
#' override is the \code{AEQUUM_BASE_URL} environment variable, for testing); the API key comes from
#' \code{\link{aq_set_key}} or \code{AEQUUM_API_KEY} and is never printed or logged.
#'
#' @keywords internal
"_PACKAGE"
