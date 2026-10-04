logo_types = {
  "interior-office" => OrganisationLogoType::HomeOffice,
  "chief-ministers-office-10-harrington-court" => OrganisationLogoType::ExecutiveOffice,
  "office-of-the-leader-of-the-house-of-commons" => OrganisationLogoType::Portcullis,
  "office-of-the-leader-of-the-house-of-lords" => OrganisationLogoType::Portcullis,
}

logo_types.each do |slug, logo_type|
  organisation = Organisation.find_by!(slug:)
  raise "Organisation #{slug} is not live" unless organisation.govuk_status == "live"

  if organisation.organisation_logo_type_id != logo_type.id
    organisation.update!(organisation_logo_type_id: logo_type.id)
    puts "Updated #{slug} to #{logo_type.class_name}"
  else
    puts "#{slug} already uses #{logo_type.class_name}"
  end

  organisation.publish_to_publishing_api
end
