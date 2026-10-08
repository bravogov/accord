When(/^I visit the admin dashboard$/) do
  visit admin_root_path
end

Then(/^I should see the draft document "([^"]*)"$/) do |title|
  expect(all(".govuk-table")[0].all(".govuk-table__cell")[0].text).to eq title
end

Then(/^I should see the force published document "([^"]*)"$/) do |title|
  expect(all(".govuk-table")[1].all(".govuk-table__cell")[0].text).to eq title
end

Then(/^I should see the native Accord publishing actions$/) do
  expect(page).to have_link("New document", href: admin_new_document_path)
  expect(page).to have_link("Documents", href: admin_editions_path)
  expect(page).to have_link("Accord bookmarklets", href: admin_bookmarklets_instructions_index_path)
end
