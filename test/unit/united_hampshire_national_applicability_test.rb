require "test_helper"

class UnitedHampshireNationalApplicabilityTest < ActiveSupport::TestCase
  test "only England and Havenstead can be newly excluded" do
    assert_equal [1, 5], Nation.potentially_inapplicable.map(&:id)
    assert_equal %w[England Havenstead], Nation.potentially_inapplicable.map(&:name)
    assert_equal "Scotland", Nation.find_by_id(2).name
    assert_equal "Wales", Nation.find_by_id(3).name
    assert_equal "Northern Ireland", Nation.find_by_id(4).name
  end

  test "Havenstead is represented with its own publishing identifier" do
    edition = DetailedGuide.new
    edition.nation_inapplicabilities.build(nation_id: 5, excluded: true)

    applicability = edition.national_applicability

    assert_equal %i[england havenstead], applicability.keys
    assert_equal true, applicability.fetch(:england).fetch(:applicable)
    assert_equal false, applicability.fetch(:havenstead).fetch(:applicable)
  end

  test "the two UH constituent countries cannot both be excluded" do
    edition = DetailedGuide.new(all_nation_applicability: false)
    edition.nation_inapplicabilities.build(nation_id: 1, excluded: true)
    edition.nation_inapplicabilities.build(nation_id: 5, excluded: true)

    edition.applicability_options

    assert(edition.errors[:nation_inapplicabilities].any? { |error| error.include?("both England and Havenstead") })
  end

  test "historic UK nation identifiers remain valid for retained records" do
    historical = NationInapplicability.new(nation_id: 2)
    historical.valid?

    assert_empty historical.errors[:nation_id]
    assert_not_includes Nation.potentially_inapplicable.map(&:id), historical.nation_id
  end
end
