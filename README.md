# Accord

Accord is United Hampshire's government publishing application for authorised editors to create, manage, review and publish government content. It is maintained as `bravogov/accord`, derived from the original `alphagov/whitehall` source and commit history.

The upstream application was named Whitehall. Existing Ruby constants, database tables, interfaces and source identifiers bearing that name are retained where required for compatibility; they do not designate the public UH application identity.

Human editors own substantive organisation, minister, role, people and publication records. Software changes must not insert parallel authoritative content outside the native publishing workflow.

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
