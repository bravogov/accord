#!/usr/bin/env ruby
# Lightweight no-database UH editor source checks. Full Rails tests remain authoritative.
root = File.expand_path("..", __dir__)
guard = File.join(root, "test/unit/uh_editor_identity_copy_test.rb")
abort("UH editor identity test missing") unless File.file?(guard)

entries = File.read(guard).scan(/^\s+"([^"]+)"\s*=>\s*"([^"]+)",?\s*$/)
abort("Expected 19 or more guarded source locations, got #{entries.length}") if entries.length < 19

entries.each do |relative, obsolete|
  path = File.join(root, relative)
  abort("Missing editor template #{relative}") unless File.file?(path)
  abort("Obsolete UK identity remains in #{relative}: #{obsolete}") if File.read(path).include?(obsolete)
end

dashboard = File.read(File.join(root, "app/views/admin/dashboard/index.html.erb"))
%w[admin_new_document_path admin_editions_path admin_bookmarklets_instructions_index_path].each do |route|
  abort("Native editorial dashboard link missing: #{route}") unless dashboard.include?(route)
end

content_tagger = File.read(File.join(root, "app/views/admin/shared/tagging/_taxonomy_group_description.html.erb"))
abort("UH Content Tagger entry missing") unless content_tagger.include?("https://content-tagger.publishing.service.gov.uhrblx.com/")
abort("Incorrect UK external service link remains in taxonomy help") if content_tagger.include?("https://www.gov.uk")

readme = File.read(File.join(root, "README.md"))
abort("Accord original Whitehall provenance missing") unless readme.include?("alphagov/whitehall")
abort("Upstream licence missing") unless File.file?(File.join(root, "LICENCE")) || File.file?(File.join(root, "LICENSE"))

abort("Do not inject a separate National Archives publisher into Accord") if Dir.exist?(File.join(root, "apps/national-archives"))
puts "Accord UH native editorial source checks passed (#{entries.length} guarded locations)."
