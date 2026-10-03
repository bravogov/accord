# Accord

Accord is the United Hampshire government publishing application, derived from the original Whitehall software maintained by [alphagov](https://github.com/alphagov/whitehall). It is used by authorised publishers to create and manage government content for GOV.UH.

This repository preserves the upstream project's history and [MIT licence](LICENCE). References to Whitehall in original internal code, interfaces and development documentation are retained until a reviewed compatibility change is required. The original upstream development instructions below remain as provenance and do not establish the GOV.UH production deployment procedure.

## Running the Application

**Use [GOV.UK Docker](https://github.com/alphagov/govuk-docker) to run any commands that follow.**

## Technical documentation

This is a Ruby on Rails app, and should follow [our Rails app conventions](https://docs.publishing.service.gov.uk/manual/conventions-for-rails-applications.html).

You can use the [GOV.UK Docker environment](https://github.com/alphagov/govuk-docker) to run the application and its tests with all the necessary dependencies. Follow [the usage instructions](https://github.com/alphagov/govuk-docker#usage) to get started.

### Running the test suite

These commands assume you have the [GOV.UK Docker environment](https://github.com/alphagov/govuk-docker) running and its binaries in your PATH.

```
# run all the test suites
govuk-docker-run bundle exec rake
```

Javascript unit tests can also be run separately:

```
# run all the JavaScript tests
govuk-docker-run bundle exec rake jasmine
```

### Further documentation

See the [`docs/`](docs/) directory.

- [Content Audit Trail](docs/auditing.md)
- [CSS](docs/css.md)
- [Edition model](docs/edition_model.md)
- [Edition workflow](docs/edition_workflow.md)
- [Internationalisation](docs/internationalisation_guide.md)
- [JavaScript](docs/javascript.md)
- [Timestamps](docs/timestamps.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Adding a data migration](db/data_migration/README.md)

## Licence

[MIT License](LICENCE)
