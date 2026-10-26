# httptest2 serves the fixture in tests/testthat/api.aequum.ai/v1/: the directory name IS the default
# service host, so this also proves the built-in address, and that health needs no key.
test_that("aq_health() reads the default host without a key", {
  skip_if_not_installed("httptest2")
  local_aq()
  httptest2::with_mock_api({
    h <- aq_health()
    expect_true(h$ok)
    expect_true(h$ready)
  })
})
