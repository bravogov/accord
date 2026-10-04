require "fast_test_helper"
require "digest"

class UhSharedIdentitySourceTest < Minitest::Test
  def component_directory
    Bundler.load.specs.find_by_name("govuk_publishing_components").full_gem_path
  end

  def test_approved_uh_header_crown_is_installed
    asset = File.join(component_directory, "app/assets/images/govuk_publishing_components/uh_header_crown.png")
    assert_equal "293218916b282a75c89326fab581942fe1f46652a32d122c17d47c9545398675", Digest::SHA256.file(asset).hexdigest
  end

  def test_approved_uh_government_arms_are_installed
    asset = File.join(component_directory, "app/assets/images/govuk_publishing_components/uh_footer_arms.webp")
    assert_equal "bd1ff9f66f8cc1d421f65d09ec3a0b53bed34c2f88c3dea1eb2317a358db7804", Digest::SHA256.file(asset).hexdigest
  end

  def test_native_wordmark_identifies_govuh
    partial = File.read(File.join(component_directory, "app/views/govuk_publishing_components/components/govuk_logo/_govuk_logo.html.erb"))
    assert_includes partial, 'aria-label="GOV.UH"'
    refute_includes partial, 'aria-label="GOV.UK"'
  end
end
