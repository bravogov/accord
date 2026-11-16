# frozen_string_literal: true
# Isolated genuine Whitehall intake logic, no writes to production services.
require "json"
require "pathname"
require "ostruct"
require "digest"
require "active_support/core_ext/object/blank"
require_relative "../../app/services/uh_document_production/source_backed_attachment_intake"

class HtmlAttachment
  attr_accessor :title, :attachable, :body, :id
  def initialize(title:, attachable:, body:, id:)
    @title, @attachable, @body, @id = title, attachable, body, id
  end
end
class FileAttachment
  attr_accessor :title, :attachable, :id, :attachment_data
  def initialize(title:, attachable:, id:, data:)
    @title, @attachable, @id, @attachment_data = title, attachable, id, data
  end
  def pdf? = true
end
class Publication
  attr_reader :title, :id, :document_id, :state
  attr_accessor :attachments
  def initialize(title, attachments: [], editable: true)
    @title, @id, @document_id, @state = title, 138, 72, "draft"
    @attachments, @editable = attachments, editable
  end
  def lead_organisations
    [OpenStruct.new(name:"Cabinet Office"), OpenStruct.new(name:"England Office"), OpenStruct.new(name:"Ministry of Infrastructure, Communities and Local Government")]
  end
  def editable? = @editable
  def allows_attachment_type?(type) = %w[html file].include?(type)
end

root = Pathname.new(ENV.fetch("UH_DOCS_QA_FIXTURES"))
revision = ENV.fetch("UH_DOCS_SOURCE_VERSION", "legacy")
if revision == "47"
  source = root.join("source/google-doc-revision-47-20261106.docx")
  govspeak = root.join("artifacts/native-govspeak-revision-47.txt")
  pdf = root.join("artifacts/government-across-united-hampshire-revision-47-pdfa2b-pdfua1.pdf")
  manifest = JSON.parse(root.join("source/manifest-google-drive-revision-47.json").read)
  proof = JSON.parse(root.join("checks/revision-47-pdf-compliance-parity-20261106.json").read)
else
  source = root.join("source/original-google-doc-revision.docx")
  govspeak = root.join("artifacts/native-govspeak.txt")
  pdf = root.join("artifacts/government-across-united-hampshire-accessible-pdfa2b-pdfua1-20261106.pdf")
  manifest = JSON.parse(root.join("sample/source-manifest.json").read)
  proof = JSON.parse(root.join("checks/pdf-compliance-parity-20261106.json").read)
end
qualified = manifest.merge(
  "pdf_sha256" => proof.fetch("pdf_sha256"),
  "pdf_accessibility_proof" => proof.fetch("pdf_accessibility_proof")
)
edition = Publication.new(manifest.fetch("title"))
allow = ->(action, _edition, _actor) { %i[update see].include?(action) }
deny = ->(_action, _edition, _actor) { false }
errors = []
pass = 0

def intake(edition, source, govspeak, pdf, manifest, authorizer)
  UhDocumentProduction::SourceBackedAttachmentIntake.new(
    edition: edition, source_path: source, govspeak_path: govspeak,
    manifest: manifest, pdf_path: pdf, authorizer: authorizer, actor: :staff
  )
end

def check(description, errors)
  yield
  puts "PASS #{description}"
  true
rescue => e
  errors << [description, e.class.to_s, e.message]
  puts "FAIL #{description}: #{e.class} #{e.message}"
  false
end
def rejects
  yield
  raise "Unexpectedly accepted invalid operation"
rescue UhDocumentProduction::SourceBackedAttachmentIntake::Rejected
  true
end

[
  ["original source qualified PDF/A+PDF/UA passes", -> { intake(edition,source,govspeak,pdf,qualified,allow).validate! }],
  ["wrong official issuing institution denied", -> { rejects {intake(edition,source,govspeak,pdf,qualified.merge("organisations"=>["Different department"]),allow).validate!} }],
  ["denied role cannot create", -> { rejects {intake(edition,source,govspeak,pdf,qualified,deny).validate!} }],
  ["uneditable edition cannot create", -> { rejects {intake(Publication.new(edition.title,editable:false),source,govspeak,pdf,qualified,allow).validate!} }],
  ["missing PDF/A proof denies", -> { rejects {intake(edition,source,govspeak,pdf,qualified.merge("pdf_accessibility_proof" => qualified["pdf_accessibility_proof"].reject{|k,v|k=="pdfa_verified"}),allow).validate!} }],
  ["missing PDF/UA proof denies", -> { rejects {intake(edition,source,govspeak,pdf,qualified.merge("pdf_accessibility_proof" => qualified["pdf_accessibility_proof"].reject{|k,v|k=="pdfua_verified"}),allow).validate!} }],
  ["wrong PDF checksum denies", -> { rejects {intake(edition,source,govspeak,pdf,qualified.merge("pdf_sha256" => "f"*64),allow).validate!} }],
  ["wrong original source checksum denies", -> { rejects {intake(edition,source,govspeak,pdf,qualified.merge("source_sha256" => "f"*64),allow).validate!} }],
  ["source body without H1 in native attachment passes", -> { raise "Unexpected H1" if govspeak.read.lines.any?{|l|l.start_with?("# ")} }],
  ["fake news article content type denies", -> { rejects {intake(edition,source,govspeak,pdf,qualified.merge("native_content_type" => "NewsArticle"),allow).validate!} }],
  ["invalid file type denies", -> { rejects {intake(edition,source,govspeak,source,qualified,allow).validate!} }],
  ["duplicate native HTML attachment denies", -> {
    e=Publication.new(edition.title)
    e.attachments << HtmlAttachment.new(title:edition.title,attachable:e,body:govspeak.read,id:19)
    rejects {intake(e,source,govspeak,pdf,qualified,allow).validate!}
  }],
  ["duplicate native PDF attachment denies", -> {
    e=Publication.new(edition.title)
    e.attachments << FileAttachment.new(title:edition.title,attachable:e,id:20,data:OpenStruct.new)
    rejects {intake(e,source,govspeak,pdf,qualified,allow).validate!}
  }],
  ["readback preserves original identifiers without writes", -> {
    e=Publication.new(edition.title)
    data=OpenStruct.new(assets:[OpenStruct.new(asset_manager_id:"6aed0f19d937becf46861e13",filename:"original.pdf",variant:"original")])
    def data.all_asset_variants_uploaded? = true
    html=HtmlAttachment.new(title:e.title,attachable:e,body:govspeak.read,id:19)
    file=FileAttachment.new(title:e.title,attachable:e,id:20,data:data)
    result=intake(e,source,govspeak,pdf,qualified,allow).readback_existing!(html_attachment:html,file_attachment:file)
    raise "Incorrect IDs #{result.inspect}" unless result.values_at(:document_id,:edition_id,:html_attachment_id,:file_attachment_id)==[72,138,19,20]
    raise "Asset lost" unless result[:asset_manager_ids]==["6aed0f19d937becf46861e13"]
  }],
  ["direct Asset Manager ID readback denied without actor permission", -> {
    e=Publication.new(edition.title)
    data=OpenStruct.new(assets:[OpenStruct.new(asset_manager_id:"sensitive-id",filename:"draft.pdf",variant:"original")])
    def data.all_asset_variants_uploaded? = true
    file=FileAttachment.new(title:e.title,attachable:e,id:20,data:data)
    rejects {intake(e,source,govspeak,pdf,qualified,deny).asset_readback!(file)}
  }],
  ["direct cross-edition Asset Manager ID readback denied", -> {
    e=Publication.new(edition.title)
    other=Publication.new(edition.title)
    data=OpenStruct.new(assets:[OpenStruct.new(asset_manager_id:"sensitive-id",filename:"draft.pdf",variant:"original")])
    def data.all_asset_variants_uploaded? = true
    file=FileAttachment.new(title:e.title,attachable:other,id:20,data:data)
    rejects {intake(e,source,govspeak,pdf,qualified,allow).asset_readback!(file)}
  }],
  ["finished flag without original asset denied", -> {
    e=Publication.new(edition.title)
    data=OpenStruct.new(assets:[OpenStruct.new(asset_manager_id:"sensitive-id",filename:"draft.pdf",variant:"thumbnail")])
    def data.all_asset_variants_uploaded? = true
    file=FileAttachment.new(title:e.title,attachable:e,id:20,data:data)
    rejects {intake(e,source,govspeak,pdf,qualified,allow).asset_readback!(file)}
  }],
  ["upload flags without asset list denied", -> {
    e=Publication.new(edition.title)
    data=OpenStruct.new(assets:[])
    def data.all_asset_variants_uploaded? = true
    file=FileAttachment.new(title:e.title,attachable:e,id:20,data:data)
    rejects {intake(e,source,govspeak,pdf,qualified,allow).asset_readback!(file)}
  }],
  ["original asset missing filename denied", -> {
    e=Publication.new(edition.title)
    data=OpenStruct.new(assets:[OpenStruct.new(asset_manager_id:"sensitive-id",filename:"",variant:"original")])
    def data.all_asset_variants_uploaded? = true
    file=FileAttachment.new(title:e.title,attachable:e,id:20,data:data)
    rejects {intake(e,source,govspeak,pdf,qualified,allow).asset_readback!(file)}
  }],
  ["denied actor cannot read existing IDs", -> {
    e=Publication.new(edition.title)
    data=OpenStruct.new(assets:[])
    def data.all_asset_variants_uploaded? = true
    html=HtmlAttachment.new(title:e.title,attachable:e,body:govspeak.read,id:19)
    file=FileAttachment.new(title:e.title,attachable:e,id:20,data:data)
    rejects {intake(e,source,govspeak,pdf,qualified,deny).readback_existing!(html_attachment:html,file_attachment:file)}
  }],
  ["cross-organisation attachment readback denied", -> {
    e=Publication.new(edition.title)
    other=Publication.new(edition.title)
    html=HtmlAttachment.new(title:e.title,attachable:other,body:govspeak.read,id:19)
    file=FileAttachment.new(title:e.title,attachable:e,id:20,data:OpenStruct.new)
    rejects {intake(e,source,govspeak,pdf,qualified,allow).readback_existing!(html_attachment:html,file_attachment:file)}
  }],
  ["incomplete Asset Manager upload cannot be read as ready", -> {
    e=Publication.new(edition.title)
    data=OpenStruct.new(assets:[])
    def data.all_asset_variants_uploaded? = false
    html=HtmlAttachment.new(title:e.title,attachable:e,body:govspeak.read,id:19)
    file=FileAttachment.new(title:e.title,attachable:e,id:20,data:data)
    rejects {intake(e,source,govspeak,pdf,qualified,allow).readback_existing!(html_attachment:html,file_attachment:file)}
  }],
  ["HTML edit mismatch denies readback", -> {
    e=Publication.new(edition.title)
    html=HtmlAttachment.new(title:e.title,attachable:e,body:"truncated",id:19)
    file=FileAttachment.new(title:e.title,attachable:e,id:20,data:OpenStruct.new)
    rejects {intake(e,source,govspeak,pdf,qualified,allow).readback_existing!(html_attachment:html,file_attachment:file)}
  }],
].each do |label, fn|
  pass += 1 if check(label, errors, &fn)
end
puts "RESULT #{pass}/#{pass + errors.length}"
abort("Candidate native intake rejected scenarios failed") if errors.any?
