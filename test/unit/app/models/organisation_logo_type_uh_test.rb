require "test_helper"

class OrganisationLogoTypeUhTest < ActiveSupport::TestCase
  test "uses established United Hampshire organisation crest labels" do
    assert_equal "United Hampshire Government (single identity)", OrganisationLogoType::SingleIdentity.title
    assert_equal "Interior Office", OrganisationLogoType::HomeOffice.title
    assert_equal "Parliament", OrganisationLogoType::Portcullis.title
    assert_equal "Chief Minister’s Office, 10 Harrington Court", OrganisationLogoType::PrimeMinistersOffice10DowningStreet.title
    assert_equal "Government Digital Service", OrganisationLogoType::GdsCrest.title
  end

  test "preserves native crest class names consumed by publishing components" do
    assert_equal "ho", OrganisationLogoType::HomeOffice.class_name
    assert_equal "eo", OrganisationLogoType::ExecutiveOffice.class_name
    assert_equal "portcullis", OrganisationLogoType::Portcullis.class_name
  end
end
