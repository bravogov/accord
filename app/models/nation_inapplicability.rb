class NationInapplicability < ApplicationRecord
  delegate :name, to: :nation

  belongs_to :edition

  scope :for_nation,
        lambda { |nation|
          where(nation_id: nation.id)
        }

  validate :nation_is_current_or_retained_historical

  def nation_is_current_or_retained_historical
    return if Nation.potentially_inapplicable.map(&:id).include?(nation_id)

    # Old published records keep their original UK nation ID and label.
    # New editions cannot create a legacy exclusion.
    historical_ids = Nation.legacy_historical.map(&:id) - Nation.potentially_inapplicable.map(&:id)
    return if persisted? && historical_ids.include?(nation_id)

    errors.add(:nation_id, "must be England or Havenstead")
  end
  validates :alternative_url, uri: true, allow_blank: true

  attr_accessor :excluded

  def excluded?
    @excluded.present? ? ActiveRecord::Type::Boolean.new.deserialize(@excluded) : persisted?
  end

  def nation
    Nation.find_by_id(nation_id)
  end

  def nation=(new_nation)
    self.nation_id = new_nation.id
  end
end
