require "test_helper"

class Admin::DashboardControllerTest < ActionController::TestCase
  setup do
    login_as :writer

    organisation = create(:organisation, users: [@current_user])
    @draft_edition1 = create(:consultation, authors: [@current_user])
    @draft_edition2 = create(:consultation, authors: [@current_user])

    @force_published_edition1 = build(
      :consultation,
      :published,
      force_published: true,
    )
    @force_published_edition2 = build(
      :consultation,
      :published,
      force_published: true,
    )

    draft_test_type = build_configurable_document_type("draft_test_type", { "title" => "Draft Test Type" })
    ConfigurableDocumentType.setup_test_types(build_configurable_document_type("force_published_test_type", { "title" => "Force Published Test Type" }).merge(draft_test_type))
    @draft_standard_edition = create(
      :draft_standard_edition,
      authors: [@current_user],
      configurable_document_type: "draft_test_type",
    )
    @force_published_standard_edition = build(
      :force_published_standard_edition,
      configurable_document_type: "force_published_test_type",
    )

    create(:edition_organisation, edition: @force_published_edition1, organisation:)
    create(:edition_organisation, edition: @force_published_edition2, organisation:)
    create(:edition_organisation, edition: @force_published_standard_edition, organisation:)
  end

  should_be_an_admin_controller

  test "GET :index" do
    get :index

    assert_response :success
    assert_template :index

    assert_select "a", text: "New document", count: 1
    assert_select "a", text: "Documents", count: 1
    assert_select "h2", text: "Writing and publishing", count: 1
    assert_select "h2", text: "Product development", count: 1
    assert_select "h2", text: "Support", count: 1
    assert_select "a[href='https://guidance.publishing.service.gov.uhrblx.com/writing-to-gov-uh-standards/']", text: "GOV.UH writing standards", count: 1
    assert_select "a[href='https://guidance.publishing.service.gov.uhrblx.com/publish-update-retire-content/']", text: "GOV.UH content and publishing guidance", count: 1
    assert_select "a[href='https://guidance.publishing.service.gov.uhrblx.com/accounts-support/']", text: "Accounts and support", count: 1
    assert_select "a", text: "Accord bookmarklets", count: 1
    assert_select "a", text: "What's new", count: 1

    assert_select "a", text: "GOV.UK style guide", count: 0
    assert_select "a", text: "GDS support form (Zendesk)", count: 0
    assert_select "a", text: "Inside GOV.UK blog", count: 0
    assert_equal [@draft_standard_edition, @draft_edition2, @draft_edition1], assigns(:draft_documents)
    assert_equal [@force_published_standard_edition, @force_published_edition2, @force_published_edition1], assigns(:force_published_documents)
  end
end
