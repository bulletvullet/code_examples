Feature: Cashback

  @good_case
  Scenario: Activate cashback offer for user
    Given new authenticated user
    And user has <INDIVIDUAL> customer
    And cashback category and merchant are added
    And created offer <offer1>
    Given activated card for <INDIVIDUAL> customer
    When activate cashback for user with offer <offer1>
    Then response status code is <200>

  @good_case
  Scenario: Activate another cashback offer cashback when first the is active
    Given new authenticated user
    And user has <INDIVIDUAL> customer
    And cashback category and merchant are added
    And created offer <offer1>
    And created offer <offer2>
    Given activated card for <INDIVIDUAL> customer
    When activate cashback for user with offer <offer1>
    Then response status code is <200>
    When activate cashback for user with offer <offer2>
    Then response status code is <200>

  @good_case
  Scenario: Successfully get cashback for transaction (Individual account)
    Given new authenticated user
    And user has <INDIVIDUAL> <BANK> account
    And cashback category and merchant are added
    And created offer <offer1> where min purchase is 20$
    Given activated card for <INDIVIDUAL> customer
    When activate cashback for user with offer <offer1>
    Then response status code is <200>
    When user created transaction on <-21>$ by <INDIVIDUAL> <BANK> account
    When cashback for transaction was checked
    Then cashback history count is <1>

  @good_case
  Scenario: Successfully get cashback for transaction (Business account)
    Given new authenticated user
    And user has <BUSINESS> <BANK> account
    And cashback category and merchant are added
    And created offer <offer1> where min purchase is 20$
    Given activated card for <BUSINESS> customer
    When activate cashback for user with offer <offer1>
    Then response status code is <200>
    When user created transaction on <-21>$ by <BUSINESS> <BANK> account
    When cashback for transaction was checked
    Then cashback history count is <1>

  @bad_case
  Scenario: Deactivate cashback immediately after activating(Only finished offer can be deactivate)
    Given new authenticated user
    And user has <INDIVIDUAL> customer
    And cashback category and merchant are added
    And created offer <offer1>
    Given activated card for <INDIVIDUAL> customer
    When activate cashback for user with offer <offer1>
    Then response status code is <200>
    When deactivate cashback for user with offer <offer1>
    Then response status code is <400>

  @bad_case
  Scenario: Unsuccessfully get cashback for transaction (less transaction amount then in offer)
    Given new authenticated user
    And user has <INDIVIDUAL> <BANK> account
    And cashback category and merchant are added
    And created offer <offer1> where min purchase is 20$
    Given activated card for <INDIVIDUAL> customer
    When activate cashback for user with offer <offer1>
    Then response status code is <200>
    When user created transaction on <-19>$ by <INDIVIDUAL> <BANK> account
    When cashback for transaction was checked
    Then cashback history count is <0>

  @bad_case
  Scenario: Unsuccessfully get cashback for transaction (positive transaction amount)
    Given new authenticated user
    And user has <INDIVIDUAL> <BANK> account
    And cashback category and merchant are added
    And created offer <offer1> where min purchase is 20$
    Given activated card for <INDIVIDUAL> customer
    When activate cashback for user with offer <offer1>
    Then response status code is <200>
    When user created transaction on <20>$ by <INDIVIDUAL> <BANK> account
    When cashback for transaction was checked
    Then cashback history count is <0>

  @bad_case
  Scenario: Cashback was not added for transaction (cashback was not activated)
    Given new authenticated user
    And user has <INDIVIDUAL> <BANK> account
    And cashback category and merchant are added
    And created offer <offer1> where min purchase is 20$
    Given activated card for <INDIVIDUAL> customer
    When user created transaction on <-21>$ by <INDIVIDUAL> <BANK> account
    When cashback for transaction was checked
    Then cashback history count is <0>