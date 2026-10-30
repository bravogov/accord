module TestsForNationalApplicability
  extend ActiveSupport::Concern

  included do
    view_test "new displays UH national applicability fields" do
      get :new

      assert_select "form#new_edition" do
        assert_nation_inapplicability_fields_exist
      end
    end

    test "create saves a Havenstead exclusion" do
      create(:government)
      attributes = attributes_for_edition

      post :create, params: {
        edition: attributes.merge(
          all_nation_applicability: %w[havenstead],
        ).merge(nation_inapplicabilities_attributes_for(Nation.havenstead => "https://www.example.com/havenstead")),
      }

      assert edition = Edition.last
      assert havenstead = edition.nation_inapplicabilities.for_nation(Nation.havenstead).first
      assert_equal "https://www.example.com/havenstead", havenstead.alternative_url
    end

    test "national applicability publishes England and Havenstead" do
      exclusion = create(
        :nation_inapplicability,
        nation: Nation.havenstead,
        alternative_url: "https://www.example.com/havenstead",
      )
      guide = create(
        :published_detailed_guide_with_excluded_nations,
        nation_inapplicabilities: [exclusion],
      )

      expected = expected_national_applicability.merge(
        havenstead: {
          label: "Havenstead",
          applicable: false,
          alternative_url: "https://www.example.com/havenstead",
        },
      )
      assert_equal expected, guide.national_applicability
    end

    view_test "creating with both constituent countries excluded fails" do
      create(:government)
      attributes = attributes_for_edition(all_nation_applicability: %w[england havenstead])
      exclusions = nation_inapplicabilities_attributes_for(
        Nation.england => "https://www.example.com/england",
        Nation.havenstead => "https://www.example.com/havenstead",
      )

      post :create, params: { edition: attributes.merge(exclusions) }

      assert_nil Edition.last
      assert_page_has_error(/you cannot exclude both England and Havenstead/)
    end

    view_test "creating with no applicability selection fails" do
      create(:government)
      post :create, params: {
        edition: attributes_for_edition.merge(nation_inapplicabilities_attributes_for({})),
      }

      assert_nil Edition.last
      assert_page_has_error(/you must select whether this content applies to all UH nations/)
    end

    view_test "selecting all nations and excluding Havenstead fails" do
      create(:government)
      post :create, params: {
        edition: attributes_for_edition.merge(
          all_nation_applicability: %w[all_nations havenstead],
        ).merge(nation_inapplicabilities_attributes_for(Nation.havenstead => "https://www.example.com/havenstead")),
      }

      assert_page_has_error(/you cannot select all UH nations and also exclude a constituent country/)
    end

    view_test "invalid edition data retains the Havenstead input values" do
      attributes = attributes_for_edition(all_nation_applicability: %w[havenstead])
      post :create, params: {
        edition: attributes.merge(title: "")
          .merge(nation_inapplicabilities_attributes_for(Nation.havenstead => "https://www.example.com/havenstead")),
      }

      assert_nation_inapplicability_fields_exist
      assert_nation_inapplicability_fields_set_as(index: 0, checked: false)
      assert_nation_inapplicability_fields_set_as(index: 1, checked: false)
      assert_nation_inapplicability_fields_set_as(index: 2, checked: true, alternative_url: "https://www.example.com/havenstead")
    end

    view_test "invalid Havenstead alternative URL retains input values" do
      attributes = attributes_for_edition(all_nation_applicability: %w[havenstead])
      post :create, params: {
        edition: attributes.merge(
          nation_inapplicabilities_attributes_for(Nation.havenstead => "invalid-url"),
        ),
      }

      assert_nation_inapplicability_fields_exist
      assert_nation_inapplicability_fields_set_as(index: 0, checked: false)
      assert_nation_inapplicability_fields_set_as(index: 1, checked: false)
      assert_nation_inapplicability_fields_set_as(index: 2, checked: true, alternative_url: "invalid-url")
    end

    view_test "edit shows the saved Havenstead exclusion" do
      edition = create_edition(all_nation_applicability: "1")
      edition.update_column(:all_nation_applicability, false)
      edition.nation_inapplicabilities.create!(
        nation: Nation.havenstead,
        alternative_url: "https://www.example.com/havenstead",
      )

      get :edit, params: { id: edition }

      assert_select "form#edit_edition" do
        assert_nation_inapplicability_fields_exist
        assert_nation_inapplicability_fields_set_as(index: 0, checked: false)
        assert_nation_inapplicability_fields_set_as(index: 1, checked: false)
        assert_nation_inapplicability_fields_set_as(index: 2, checked: true, alternative_url: "https://www.example.com/havenstead")
      end
    end

    test "update replaces a Havenstead exclusion with England" do
      edition = create_edition(all_nation_applicability: "1")
      edition.update_column(:all_nation_applicability, false)
      havenstead = edition.nation_inapplicabilities.create!(
        nation: Nation.havenstead,
        alternative_url: "https://www.example.com/havenstead",
      )
      edition.save!

      attributes = nation_inapplicabilities_attributes_for(
        { Nation.england => "https://www.example.com/england" },
        havenstead,
      ).merge(all_nation_applicability: %w[england])

      put :update, params: { id: edition, edition: attributes }

      edition.reload
      assert_equal [Nation.england], edition.inapplicable_nations
      assert_equal "https://www.example.com/england", edition.nation_inapplicabilities.for_nation(Nation.england).first.alternative_url
    end

    view_test "invalid edit retains Havenstead inputs" do
      edition = create_edition(all_nation_applicability: "1")
      edition.update_column(:all_nation_applicability, false)
      havenstead = edition.nation_inapplicabilities.create!(
        nation: Nation.havenstead,
        alternative_url: "https://www.example.com/havenstead",
      )
      edition.save!

      attributes = nation_inapplicabilities_attributes_for(
        { Nation.havenstead => "https://www.example.com/havenstead" },
        havenstead,
      ).merge(title: "", all_nation_applicability: %w[havenstead])

      put :update, params: { id: edition, edition: attributes }

      assert_page_has_error(/Title cannot be blank/)
      assert_nation_inapplicability_fields_exist
      assert_nation_inapplicability_fields_set_as(index: 2, checked: true, alternative_url: "https://www.example.com/havenstead")
    end

    view_test "invalid edited alternative URL is not discarded" do
      edition = create_edition(all_nation_applicability: "1")
      edition.update_column(:all_nation_applicability, false)
      havenstead = edition.nation_inapplicabilities.create!(
        nation: Nation.havenstead,
        alternative_url: "https://www.example.com/havenstead",
      )

      attributes = nation_inapplicabilities_attributes_for(
        { Nation.havenstead => "invalid-url" },
        havenstead,
      ).merge(all_nation_applicability: %w[havenstead])

      put :update, params: { id: edition, edition: attributes }

      assert_nation_inapplicability_fields_exist
      assert_nation_inapplicability_fields_set_as(index: 2, checked: true, alternative_url: "invalid-url")
    end

    view_test "stale edits retain Havenstead inputs" do
      edition = create_edition(all_nation_applicability: "1")
      edition.update_column(:all_nation_applicability, false)
      havenstead = edition.nation_inapplicabilities.create!(
        nation: Nation.havenstead,
        alternative_url: "https://www.example.com/havenstead",
      )
      lock_version = edition.lock_version
      edition.update!(title: "new title", change_note: "foo")

      attributes = nation_inapplicabilities_attributes_for(
        { Nation.havenstead => "https://www.example.com/havenstead" },
        havenstead,
      ).merge(lock_version:, all_nation_applicability: %w[havenstead])

      put :update, params: { id: edition, edition: attributes }

      assert_nation_inapplicability_fields_exist
      assert_nation_inapplicability_fields_set_as(index: 2, checked: true, alternative_url: "https://www.example.com/havenstead")
    end
  end

private

  def expected_national_applicability
    {
      england: {
        label: "England",
        applicable: true,
      },
      havenstead: {
        label: "Havenstead",
        applicable: true,
      },
    }
  end

  def attributes_for_edition(attributes = {})
    controller_attributes_for(edition_class.name.underscore, attributes)
  end

  def create_edition(attributes = {})
    create(edition_class.name.underscore, attributes)
  end

  def edition_class
    Edition
  end

  def assert_nation_inapplicability_fields_exist
    assert_select "input[id='edition_nation_inapplicabilities'][type='checkbox'][value='all_nations']", count: 1
    assert_select "input[id='edition_nation_inapplicabilities_checkboxes-1'][type='checkbox'][value='england']", count: 1
    assert_select "input[id='edition_nation_inapplicabilities_checkboxes-2'][type='checkbox'][value='havenstead']", count: 1
    assert_select "input[id='edition_nation_inapplicabilities_checkboxes_attributes_0_alternative_url'][type='text']", count: 1
    assert_select "input[id='edition_nation_inapplicabilities_checkboxes_attributes_1_alternative_url'][type='text']", count: 1
  end

  def nation_inapplicabilities_attributes_for(nations_vs_urls, *existing_applicabilities)
    nation_inapplicabilities_attributes = {}

    [Nation.england, Nation.havenstead].each.with_index do |nation, index|
      attributes = nation_inapplicabilities_attributes[index.to_s] = { nation_id: nation.id }
      existing = existing_applicabilities.detect { |item| item.nation_id == nation.id }
      if existing
        attributes[:id] = existing.id
        attributes[:alternative_url] = existing.alternative_url
      end
      new_url = nations_vs_urls[nation]
      attributes[:alternative_url] = new_url if new_url.present?
    end

    { nation_inapplicabilities_attributes: }
  end

  def assert_page_has_error(error)
    assert_select(".govuk-error-summary", text: error)
  end

  def assert_nation_inapplicability_fields_set_as(attributes)
    fragment = attributes[:index].zero? ? "edition_nation_inapplicabilities" : "edition_nation_inapplicabilities_checkboxes-#{attributes[:index]}"
    url_name = "edition[nation_inapplicabilities_attributes][#{attributes[:index] - 1}][alternative_url]"

    if attributes[:checked]
      assert_select "input[id='#{fragment}'][type='checkbox'][checked='checked']"
    else
      refute_select "input[id='#{fragment}'][type='checkbox'][checked='checked']"
      assert_select "input[id='#{fragment}'][type='checkbox']"
    end
    if attributes[:alternative_url]
      assert_select "input[name='#{url_name}'][value='#{attributes[:alternative_url]}']"
    end
  end
end
