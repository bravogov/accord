# Accord

Accord is the United Hampshire government publishing application used by authorised editors to create and manage government content for GOV.UH. It is maintained as a source-preserving fork of the original [alphagov/whitehall](https://github.com/alphagov/whitehall) application. Original upstream authorship, commit history, licence and functional integration contracts are retained.

The upstream software retains some `Whitehall` code identifiers while their replacement is individually assessed and tested; these identifiers are not the UH-facing product name.

## Running the Application

The commands below describe the original upstream GOV.UK Docker development environment. They do not constitute the accepted UH production deployment procedure. GOV.UH releases require their own tested configuration, pinned source and immutable image digest.

**Upstream development reference:** [GOV.UK Docker](https://github.com/alphagov/govuk-docker).

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
