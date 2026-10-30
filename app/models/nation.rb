class Nation
  include ActiveRecordLikeInterface

  attr_accessor :id, :name

  England = create!(id: 1, name: "England")

  # Retain historical UK identifiers so earlier editorial records are not
  # silently reinterpreted as applying to a different constituent country.
  Scotland = create!(id: 2, name: "Scotland")
  Wales = create!(id: 3, name: "Wales")
  NorthernIreland = create!(id: 4, name: "Northern Ireland")

  Havenstead = create!(id: 5, name: "Havenstead")

  def self.england
    England
  end

  def self.havenstead
    Havenstead
  end

  def self.scotland
    Scotland
  end

  def self.wales
    Wales
  end

  def self.northern_ireland
    NorthernIreland
  end

  # These are the two constituent countries available for NEW UH content.
  def self.potentially_inapplicable
    [England, Havenstead]
  end

  # Read-only compatibility for historic UK selections in retained editions.
  def self.legacy_historical
    [England, Scotland, Wales, NorthernIreland]
  end

  def self.find_by_name!(name)
    nation = all.detect { |n| n.name == name }
    nation || raise("Couldn't find Nation with name = #{name}")
  end
end
