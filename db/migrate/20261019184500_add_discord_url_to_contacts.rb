class AddDiscordUrlToContacts < ActiveRecord::Migration[8.1]
  def change
    add_column :contacts, :discord_url, :string
  end
end
