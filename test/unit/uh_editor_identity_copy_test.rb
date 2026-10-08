require "test_helper"

class UhEditorIdentityCopyTest < ActiveSupport::TestCase
  ORIGINAL_COPY = {
    "app/views/admin/standard_editions/features.html.erb" => "GOV.UK content",
    "app/views/admin/world_location_news/features.html.erb" => "GOV.UK content",
    "app/views/admin/topical_event_featurings/index.html.erb" => "GOV.UK content",
    "app/views/admin/organisations/features.html.erb" => "GOV.UK content",
    "app/views/admin/statistics_announcements/_cancel_form.html.erb" => "The announcement will remain on GOV.UK",
    "app/views/admin/html_attachments/_fields.html.erb" => "preview your document on GOV.UK",
    "app/views/admin/edition_workflow/confirm_unpublish.html.erb" => "consolidated into another GOV.UK page",
    "app/views/admin/publications/_form.html.erb" => "through GOV.UK for distribution",
    "app/views/admin/organisations/_form.html.erb" => "Status on GOV.UK",
    "app/views/admin/speeches/_delivered_by_fields.html.erb" => "profile on GOV.UK",
    "app/views/admin/statistics_announcement_unpublishings/new.html.erb" => "GOV.UK if they",
    "app/views/admin/editions/show/_sidebar_notices.html.erb" => "before on GOV.UK",
    "app/views/admin/editions/_page_address_controls.html.erb" => "Current GOV.UK URL:",
    "app/views/admin/editions/_standard_fields.html.erb" => "preview your document on GOV.UK",
    "app/views/shared/_phase_banner.html.erb" => "changes to Whitehall",
    "app/views/admin/errors/unprocessable_content.html.erb" => "support.publishing.service.gov.uk",
    "app/views/admin/errors/bad_request.html.erb" => "support.publishing.service.gov.uk",
    "app/views/admin/errors/forbidden.html.erb" => "support.publishing.service.gov.uk",
    "app/views/admin/errors/internal_server_error.html.erb" => "support.publishing.service.gov.uk",
  }.freeze

  test "editorial screens do not reintroduce obsolete UK site identity" do
    ORIGINAL_COPY.each do |path,obsolete_copy|
      content = Rails.root.join(path).read
      assert_not_includes content, obsolete_copy, "#{path} must use the UH editorial identity"
    end
  end
end
