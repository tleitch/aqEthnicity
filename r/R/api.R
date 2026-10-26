# Public functions -------------------------------------------------------------------------------

#' Service health (no key needed)
#'
#' @return A list with \code{ok}, \code{ready} (TRUE once the address tables are loaded) and the
#'   service version.
#' @examples
#' \dontrun{
#' aq_health()
#' }
#' @export
aq_health <- function() {
  .aq_request("GET", "/v1/health", needs_key = FALSE)
}

#' Bayesian Improved Surname Geocoding (BISG)
#'
#' Four-class probabilities (asian, black, hispanic, white) from a surname and a geography. Hosted:
#' an API key is required (see \code{\link{aq_set_key}}).
#'
#' @param last_name Surname(s).
#' @param zcta,tract,block_group Census geography codes (give at least one, or an address).
#' @param drop_intermediate Drop the intermediate probability columns.
#' @param address,city,state,zip5 Optionally an address instead of a GEOID; the service resolves it.
#' @param chunksize Records per request (default 1000).
#' @param ... Not used; any named argument is refused (for example \code{mname}).
#' @return A data frame, one row per input row, in input order.
#' @examples
#' \dontrun{
#' bisg("GARCIA", zcta = "11201")
#' }
#' @export
bisg <- function(last_name, zcta = NULL, tract = NULL, block_group = NULL, drop_intermediate = TRUE,
                 address = NULL, city = NULL, state = NULL, zip5 = NULL, chunksize = 1000L, ...) {
  .aq_reject_unknown(list(...), "bisg")
  cols <- .aq_columns(last_name = last_name, zcta = zcta, tract = tract, block_group = block_group,
                      address = address, city = city, state = state, zip5 = zip5)
  .aq_predict("/v1/predict/bisg", cols, list(drop_intermediate = isTRUE(drop_intermediate)), chunksize)
}

#' Bayesian Improved First Name Surname Geocoding (BIFSG)
#'
#' @inheritParams bisg
#' @param first_name First name(s).
#' @return A data frame, one row per input row, in input order.
#' @examples
#' \dontrun{
#' bifsg("MARIA", "GARCIA", zcta = "11201")
#' }
#' @export
bifsg <- function(first_name, last_name, zcta = NULL, tract = NULL, block_group = NULL,
                  drop_intermediate = TRUE, address = NULL, city = NULL, state = NULL, zip5 = NULL,
                  chunksize = 1000L, ...) {
  .aq_reject_unknown(list(...), "bifsg")
  cols <- .aq_columns(first_name = first_name, last_name = last_name, zcta = zcta, tract = tract,
                      block_group = block_group, address = address, city = city, state = state,
                      zip5 = zip5)
  .aq_predict("/v1/predict/bifsg", cols, list(drop_intermediate = isTRUE(drop_intermediate)), chunksize)
}

#' aqEthnicity STRATA
#'
#' Five-class probabilities (white, black, hispanic, asian, other), an uncertainty index
#' (\code{iu}) and the lookup level used, from a name and an address (or a census geography).
#'
#' @param first_name,last_name Names. Use these spellings: the service ignores others, so this
#'   function refuses them (for example \code{mname}; the middle name is \code{middle_name}).
#' @param middle_name Optional middle name(s).
#' @param zcta,tract,block_group Optional census geography codes.
#' @param address,city,state,zip5 Optional address; the service resolves it.
#' @param passthrough Optional named list of vectors echoed back, to line the answers up with your
#'   data. Names must not collide with the field names.
#' @param tier \code{"auto"} (the finest geography each record resolves to; default), \code{"bgt"},
#'   \code{"tract"}, \code{"zcta"} or \code{"name"}. A forced tier refuses rows that cannot resolve
#'   that finely.
#' @param model Optional model family (\code{"M8"} default or \code{"M2"}).
#' @param chunksize Records per request (default 1000).
#' @param ... Not used; any named argument is refused.
#' @return A data frame, one row per input row, in input order.
#' @examples
#' \dontrun{
#' strata("MARIA", "GARCIA", address = "9644 N 10TH AVE", city = "PHOENIX", state = "AZ",
#'        zip5 = "85021")
#' }
#' @export
strata <- function(first_name, last_name, middle_name = NULL, zcta = NULL, tract = NULL,
                   block_group = NULL, address = NULL, city = NULL, state = NULL, zip5 = NULL,
                   passthrough = NULL, tier = c("auto", "bgt", "tract", "zcta", "name"),
                   model = NULL, chunksize = 1000L, ...) {
  .aq_reject_unknown(list(...), "strata")
  tier <- match.arg(tier)
  .aq_check_passthrough(passthrough)
  cols <- .aq_columns(first_name = first_name, middle_name = middle_name, last_name = last_name,
                      zcta = zcta, tract = tract, block_group = block_group, address = address,
                      city = city, state = state, zip5 = zip5)
  n <- length(cols[[1L]])
  options <- list()
  if (!is.null(passthrough)) {
    pt <- lapply(passthrough, function(v) {
      if (length(v) != n) .aq_abort("each passthrough column must have one value per record.", "aq_error_input")
      as.character(v)
    })
    cols <- c(cols, pt)
    options$passthrough <- as.list(names(passthrough))
  }
  if (!is.null(model)) options$model <- model
  .aq_predict(paste0("/v1/strata/", tier), cols, options, chunksize)
}

#' Resolve addresses to a lookup level
#'
#' For each address: the lookup level (\code{BG}, \code{TRACT}, \code{ZIP} or \code{NONE}) and a
#' confidence. The geography itself is not returned.
#'
#' @param address,city,state,zip5 Address parts.
#' @param chunksize Records per request (default 1000).
#' @param ... Not used; any named argument is refused.
#' @return A data frame, one row per input row, in input order.
#' @examples
#' \dontrun{
#' geocode("9644 N 10TH AVE", "PHOENIX", "AZ", "85021")
#' }
#' @export
geocode <- function(address, city = NULL, state = NULL, zip5 = NULL, chunksize = 1000L, ...) {
  .aq_reject_unknown(list(...), "geocode")
  cols <- .aq_columns(address = address, city = city, state = state, zip5 = zip5)
  .aq_predict("/v1/geocode", cols, list(), chunksize)
}

#' wru-style wrapper: add probability columns to a data frame
#'
#' Scores each row of \code{voter.file} and returns it with probability columns named as in the
#' \pkg{wru} package: \code{pred.whi}, \code{pred.bla}, \code{pred.his}, \code{pred.asi},
#' \code{pred.oth}. With \code{model = "strata"} it also adds \code{pred.iu} (uncertainty index) and
#' \code{pred.level} (lookup level). BISG and BIFSG are four-class, so \code{pred.oth} is
#' \code{NA} for them.
#'
#' @param voter.file A data frame.
#' @param surname,first,middle,address,city,state,zip,zcta,tract,block_group Names of the columns of
#'   \code{voter.file} to use (character). \code{surname} is required; the others are optional
#'   (\code{NULL} = not used). Defaults follow \pkg{wru}'s column names where they exist.
#' @param model \code{"strata"} (default), \code{"bisg"} or \code{"bifsg"} (\code{"bifsg"} needs
#'   \code{first}).
#' @param chunksize Records per request (default 1000).
#' @param ... Not used; any named argument is refused (for example \code{mname}).
#' @return \code{voter.file} with the probability columns added, rows in the original order.
#' @examples
#' \dontrun{
#' df <- data.frame(surname = c("GARCIA", "SMITH"), first = c("MARIA", "JAMES"),
#'                  zip = c("11201", "60601"))
#' predict_race_aq(df, zip = "zip", model = "bifsg")
#' }
#' @export
predict_race_aq <- function(voter.file, surname = "surname", first = "first", middle = NULL,
                            address = NULL, city = NULL, state = NULL, zip = NULL, zcta = NULL,
                            tract = NULL, block_group = NULL,
                            model = c("strata", "bisg", "bifsg"), chunksize = 1000L, ...) {
  .aq_reject_unknown(list(...), "predict_race_aq")
  model <- match.arg(model)
  if (!is.data.frame(voter.file)) .aq_abort("voter.file must be a data frame.", "aq_error_input")
  mapping <- list(surname = surname, first = first, middle = middle, address = address, city = city,
                  state = state, zip = zip, zcta = zcta, tract = tract, block_group = block_group)
  col <- function(arg) {
    nm <- mapping[[arg]]
    if (is.null(nm)) return(NULL)
    if (!is.character(nm) || length(nm) != 1L) {
      .aq_abort(sprintf("'%s' must be the name of a column of voter.file.", arg), "aq_error_input")
    }
    if (!nm %in% names(voter.file)) {
      if (arg == "first" && identical(nm, "first")) return(NULL)   # the default: not mapped, not present
      .aq_abort(sprintf("column '%s' (for '%s') not found in voter.file. Columns: %s.", nm, arg,
                        paste(names(voter.file), collapse = ", ")), "aq_error_input")
    }
    voter.file[[nm]]
  }
  last <- col("surname")
  if (is.null(last)) .aq_abort("surname is required.", "aq_error_input")
  fst <- col("first"); mid <- col("middle")
  out <- switch(model,
    strata = strata(first_name = if (is.null(fst)) rep("", nrow(voter.file)) else fst, last_name = last,
                    middle_name = mid, zcta = col("zcta"), tract = col("tract"),
                    block_group = col("block_group"), address = col("address"), city = col("city"),
                    state = col("state"), zip5 = col("zip"), chunksize = chunksize),
    bisg = bisg(last, zcta = if (is.null(col("zcta"))) col("zip") else col("zcta"),
                tract = col("tract"), block_group = col("block_group"), chunksize = chunksize),
    bifsg = {
      if (is.null(fst)) .aq_abort("model = \"bifsg\" needs the first-name column (argument 'first').", "aq_error_input")
      bifsg(fst, last, zcta = if (is.null(col("zcta"))) col("zip") else col("zcta"),
            tract = col("tract"), block_group = col("block_group"), chunksize = chunksize)
    })
  get <- function(nm) if (nm %in% names(out)) out[[nm]] else rep(NA_real_, nrow(out))
  res <- voter.file
  if (model == "strata") {
    res$pred.whi <- get("p_white"); res$pred.bla <- get("p_black"); res$pred.his <- get("p_hispanic")
    res$pred.asi <- get("p_asian"); res$pred.oth <- get("p_other")
    res$pred.iu <- get("iu")
    res$pred.level <- if ("lookup_level" %in% names(out)) out[["lookup_level"]] else NA_character_
  } else {
    res$pred.whi <- get("white"); res$pred.bla <- get("black"); res$pred.his <- get("hispanic")
    res$pred.asi <- get("asian"); res$pred.oth <- NA_real_
  }
  res
}
