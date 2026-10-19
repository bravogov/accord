require "test_helper"

class ContactDiscordTest < ActiveSupport::TestCase
  test "accepts a valid Discord channel or invitation" do
    contact = Contact.new(discord_url: "https://discord.com/channels/123456789/987654321")
    contact.valid?
    assert_empty contact.errors[:discord_url]

    contact.discord_url = "https://discord.gg/OfficialInvite"
    contact.valid?
    assert_empty contact.errors[:discord_url]
  end

  test "rejects non-Discord, insecure and invalid links" do
    ["http://discord.gg/example", "https://discord.gg.evil.example/invite", "javascript:alert(1)", "not a url"].each do |url|
      contact = Contact.new(discord_url: url)
      contact.valid?
      assert_not_empty contact.errors[:discord_url], "Expected #{url} to be rejected"
    end
  end
end
