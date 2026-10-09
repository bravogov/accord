require "test_helper"

class WhatsNewTest < ActionDispatch::IntegrationTest
  test "it shows whats new page" do
    login_as create(:gds_editor)
    get admin_whats_new_path

    assert_select "h1", text: "What’s new in Accord"
    assert_select "a[href='https://guidance.publishing.service.gov.uhrblx.com/writing-to-gov-uh-standards/']", count: 1
    assert_select "a[href='https://guidance.publishing.service.gov.uhrblx.com/accounts-support/']", count: 1
    assert_select "a[href^='https://www.gov.uk']", count: 0
    assert_select "a[href*='insidegovuk.blog.gov.uk']", count: 0
  end

  test "each section has h2 and a back to top link" do
    login_as create(:gds_editor)
    get admin_whats_new_path

    assert_select ".app-view-whats-new__section" do |sections|
      sections.each do |section|
        assert_select section, "h2", count: 1
        assert_select section, ".app-view-whats-new__back-to-top-link", count: 1
      end
    end
  end
end
