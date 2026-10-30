module Edition::NationalApplicability
  extend ActiveSupport::Concern

  class Trait < Edition::Traits::Trait
    def process_associations_before_draft_creation(edition)
      @edition.nation_inapplicabilities.each do |na|
        edition.nation_inapplicabilities.build(na.attributes.except("id"))
      end
    end
  end

  included do
    validate :applicability_options
    has_many :nation_inapplicabilities, foreign_key: :edition_id, dependent: :destroy, autosave: true
    validates_associated :nation_inapplicabilities
    validates :nation_inapplicabilities, length: { maximum: Nation.legacy_historical.count - 1, message: "can not exclude all nations" }

    add_trait Trait
  end

  def applicability_options
    if !all_nation_applicability && nation_inapplicabilities.none?(&:excluded?)
      errors.add(:nation_inapplicabilities, "- you must select whether this content applies to all UH nations or which constituent country it excludes")
    end
    if all_nation_applicability && nation_inapplicabilities.any?(&:excluded?)
      errors.add(:nation_inapplicabilities, "- you cannot select all UH nations and also exclude a constituent country")
    end
    active_ids = Nation.potentially_inapplicable.map(&:id)
    selected_ids = nation_inapplicabilities.reject(&:marked_for_destruction?).select(&:excluded?).map(&:nation_id)
    if (selected_ids & active_ids).size == active_ids.size
      errors.add(:nation_inapplicabilities, "- you cannot exclude both England and Havenstead")
    end
    if (selected_ids & active_ids).any? && (selected_ids - active_ids).any?
      errors.add(:nation_inapplicabilities, "- historical UK exclusions must be reviewed separately from UH nation selections")
    end
  end

  def nation_inapplicabilities_attributes=(attributes)
    attributes.each_value do |params|
      existing = nation_inapplicabilities.detect { |ni| ni.nation_id == params[:nation_id].to_i }

      if ActiveRecord::Type::Boolean.new.deserialize(params[:excluded])
        if existing
          existing.attributes = params.except(:excluded, :id)
        else
          nation_inapplicabilities.build(params)
        end
      elsif existing
        existing.mark_for_destruction
        existing.excluded = params[:excluded]
      end
    end
  end

  def inapplicable_nations
    nation_inapplicabilities.map(&:nation)
  end

  def applicable_nations
    applicable_nation_set - inapplicable_nations
  end

  def can_apply_to_subset_of_nations?
    true
  end

  def national_applicability
    nations = universally_applicable(applicable_nation_set)

    inapplicabilities = nation_inapplicabilities
    inapplicabilities.each_with_object(nations) do |inapplicability, hash|
      key = nation_to_sym(inapplicability.nation.name)
      hash[key][:applicable] = false
      hash[key][:alternative_url] = inapplicability.alternative_url if inapplicability.alternative_url
    end
  end

private

  def nation_to_sym(nation)
    nation.tr(" ", "_").downcase.to_sym
  end

  def applicable_nation_set
    # An existing historic UK exclusion must retain its original meaning.
    # New UH editions use England and Havenstead, with distinct stable IDs.
    legacy_ids = Nation.legacy_historical.map(&:id) - Nation.potentially_inapplicable.map(&:id)
    if nation_inapplicabilities.any? { |record| legacy_ids.include?(record.nation_id) }
      Nation.legacy_historical
    else
      Nation.potentially_inapplicable
    end
  end

  def universally_applicable(nations)
    nations.each_with_object({}) do |nation, hash|
      key = nation_to_sym(nation.name)
      hash[key] = {
        label: nation.name,
        applicable: true,
      }
    end
  end
end
