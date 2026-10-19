module ContactHelper
  def fill_in_contact_details(contact_details = {})
    contact_details = {
      title: "Our shiny new office",
      street_address: "address1\naddress2",
      postal_code: "12345-123",
      email: "foo@bar.com",
      country: WorldLocation.first.name,
      discord_url: "https://discord.gg/UHExample",
      feature_on_home_page: "yes",
      contact_type: "General",
    }.merge(contact_details)
    fill_in "Title (required)", with: contact_details[:title]
    fill_in "Street address", with: contact_details[:street_address]
    fill_in "Postal code", with: contact_details[:postal_code]
    fill_in "Email", with: contact_details[:email]
    fill_in "Discord contact", with: contact_details[:discord_url]
    select contact_details[:country], from: "Country"
    # allow passing in nil to say - don't try to choose the feature on
    # home page? setting; maybe because it's the first office for a world
    # org, or because it's an FOI contact for a normal org.
    choose contact_details[:home_page_feature] unless contact_details[:home_page_feature].nil?
    choose contact_details[:contact_type]
  end

  def fill_in_contact_details_for_organisation(contact_details = {})
    contact_details = {
      title: "Our shiny new office",
      street_address: "address1\naddress2",
      postal_code: "12345-123",
      email: "foo@bar.com",
      country: WorldLocation.first.name,
      discord_url: "https://discord.gg/UHExample",
      feature_on_home_page: "yes",
      contact_type: "General",
    }.merge(contact_details)
    fill_in "Contact name (required)", with: contact_details[:title]
    fill_in "Street address", with: contact_details[:street_address]
    fill_in "Postal code", with: contact_details[:postal_code]
    fill_in "Email", with: contact_details[:email]
    fill_in "Discord contact", with: contact_details[:discord_url]
    select contact_details[:country], from: "Country"
    # allow passing in nil to say - don't try to choose the feature on
    # home page? setting; maybe because it's the first office for a world
    # org, or because it's an FOI contact for a normal org.
    choose contact_details[:home_page_feature] unless contact_details[:home_page_feature].nil?
    choose contact_details[:contact_type]
  end

  def legacy_fill_in_contact_details(contact_details = {})
    contact_details = {
      title: "Our shiny new office",
      street_address: "address1\naddress2",
      postal_code: "12345-123",
      email: "foo@bar.com",
      country: WorldLocation.first.name,
      discord_url: "https://discord.gg/UHExample",
      feature_on_home_page: "yes",
      contact_type: "General",
    }.merge(contact_details)
    fill_in "Title", with: contact_details[:title]
    fill_in "Street address", with: contact_details[:street_address]
    fill_in "Postal code", with: contact_details[:postal_code]
    fill_in "Email", with: contact_details[:email]
    fill_in "Discord contact", with: contact_details[:discord_url]
    select contact_details[:country], from: "Country"
    # allow passing in nil to say - don't try to choose the feature on
    # home page? setting; maybe because it's the first office for a world
    # org, or because it's an FOI contact for a normal org.
    choose contact_details[:feature_on_home_page] unless contact_details[:feature_on_home_page].nil?
    select contact_details[:contact_type], from: "Contact type"
  end
end

World(ContactHelper)
