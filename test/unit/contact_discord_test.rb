require "test_helper"

class ContactDiscordTest < ActiveSupport::TestCase
  test "historical telephone and Discord values are never published as contacts" do
    contact = build(:contact, discord_url: "https://discord.gg/HistoricInvite")
    contact.contact_numbers.build(label: "Historic telephone", number: "1234")

    details = PublishingApi::ContactPresenter.new(contact).send(:details)

    assert_not details.key?(:quick_links)
    assert_not details.key?(:phone_numbers)
  end
end
