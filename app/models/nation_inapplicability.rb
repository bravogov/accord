class NationInapplicability < ApplicationRecord
  delegate :name, to: :nation

  belongs_to :edition

  scope :for_nation,
        lambda { |nation|
          where(nation_id: nation.id)
        }

  # Maintain compatibility with archived UK-era editions and their original
  # publisher records. The native Accord form offers only England/Havenstead.
  validates :nation_id, inclusion: { in: Nation.all.map(&:id) }
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
