# frozen_string_literal: true

require "digest"
require "json"
require "pathname"

# Candidate-only intake adapter for Whitehall/Accord native attachment models.
# It does not publish, clear a document, appoint an editor, or mint asset IDs.
# A competent editor must use the existing native controller permission route.
module UhDocumentProduction
  class SourceBackedAttachmentIntake
    class Rejected < StandardError; end

    HTML_ATTACHMENT_TYPES = %w[Publication Consultation CallForEvidence].freeze
    HTML_ONLY_TYPES = %w[NewsArticle Manual].freeze

    def initialize(edition:, actor:, authorizer:, source_path:, manifest:, govspeak_path:, pdf_path: nil)
      @edition = edition
      @actor = actor
      @authorizer = authorizer
      @source_path = Pathname.new(source_path)
      @manifest = manifest.transform_keys(&:to_s)
      @govspeak_path = Pathname.new(govspeak_path)
      @pdf_path = pdf_path && Pathname.new(pdf_path)
    end

    def validate!
      reject!("Explicit edition update authority is required") unless @authorizer.respond_to?(:call)
      reject!("Editor cannot update this edition") unless @authorizer.call(:update, @edition, @actor)
      reject!("This edition is not editable") unless @edition.editable?
      reject!("Only unpublished candidates can be assembled") unless @manifest["status"] == "unpublished_candidate"
      type = @manifest["native_content_type"]
      reject!("Unsupported content type") unless (HTML_ATTACHMENT_TYPES + HTML_ONLY_TYPES).include?(type)
      reject!("Content type does not match native edition") unless @edition.class.name == type
      reject!("Source title does not match native edition") unless @edition.title == @manifest["title"]
      # Never silently create another set of attachments on a retry. Native
      # attachment IDs and edition history must be preserved and reconciled.
      if @edition.respond_to?(:attachments)
        existing = @edition.attachments.to_a.select do |attachment|
          attachment.title == @manifest["title"] &&
            (attachment.is_a?(HtmlAttachment) || attachment.is_a?(FileAttachment))
        end
        reject!("Existing source-backed attachments require readback, not another upload") if existing.any?
      end
      reject!("Source must be preserved") unless @source_path.file? && @source_path.size.positive?
      reject!("Invalid revision identifier") unless @manifest["source_revision"].to_s.match?(/\A[a-zA-Z0-9_:\-]{10,180}\z/)
      reject!("Source checksum mismatch") unless Digest::SHA256.file(@source_path).hexdigest == @manifest["source_sha256"]
      reject!("Missing source URL") unless @manifest["source_uri"].to_s.start_with?("https://")
      reject!("Missing issuing organisations") unless @manifest["organisations"].is_a?(Array) && @manifest["organisations"].all? { |x| x.is_a?(String) && !x.strip.empty? }
      # The actual Whitehall lead organisations, not a source-file claim, own
      # this document and determine its official identity. Never substitute
      # the generic website logo for a departmental publisher's identity.
      reject!("Native edition has no lead organisation relationship") unless @edition.respond_to?(:lead_organisations)
      native_owners = @edition.lead_organisations.map(&:name)
      reject!("Source issuer differs from native edition") unless native_owners == @manifest["organisations"]
      reject!("Source publication date missing") if @manifest["published_display"].to_s.empty?
      reject!("Source update date missing") if @manifest["updated_display"].to_s.empty?
      reject!("Govspeak body missing") unless @govspeak_path.file? && @govspeak_path.size.positive?
      body = @govspeak_path.read(encoding: "UTF-8")
      reject!("An H1 belongs in the native title field") if body.lines.any? { |x| x.match?(/\A#\s/) }
      reject!("No native body headings") unless body.lines.any? { |x| x.match?(/\A##\s/) }
      if HTML_ONLY_TYPES.include?(type)
        reject!("HTML attachments forbidden for this product type") if @manifest["html_attachment"]
        reject!("Automatic PDF forbidden for HTML-only product") if @manifest["pdf_required"]
        reject!("HTML-only content must use its own publisher") # not an attachment intake
      end
      reject!("Native content type does not permit HTML attachments") unless @edition.allows_attachment_type?("html")
      reject!("Native content type does not permit file attachments") if @pdf_path && !@edition.allows_attachment_type?("file")
      if @manifest["pdf_required"]
        reject!("Required PDF missing") unless @pdf_path&.file? && @pdf_path.size.positive?
        reject!("Not a PDF") unless @pdf_path.open("rb") { |f| f.read(5) } == "%PDF-"
        proof = @manifest["pdf_accessibility_proof"] || {}
        reject!("PDF accessibility proof missing") unless proof["tagged"] == true &&
          proof["tag_roles"].is_a?(Array) && proof["tag_roles"].include?("/H1") &&
          proof["tag_roles"].include?("/H2") && proof["pdf_language"] == "en-GB" &&
          proof["pdf_text_similarity"].to_f >= 0.995
        reject!("PDF checksum mismatch") unless Digest::SHA256.file(@pdf_path).hexdigest == @manifest["pdf_sha256"]
        reject!("Independent PDF/A-2b conformance proof missing") unless
          proof["pdfa_profile"] == "PDF/A-2b" && proof["pdfa_verified"] == true
        reject!("Independent PDF/UA-1 conformance proof missing") unless
          proof["pdfua_profile"] == "PDF/UA-1" && proof["pdfua_verified"] == true
      else
        reject!("Unrequired PDF supplied") if @pdf_path
      end
      true
    end

    # Native save for an authorised, isolated edition. Asset Manager upload is
    # asynchronous: the returned ID is the CMS file-attachment ID, not an
    # invented Asset Manager ID. No publication method is called here.
    def save_draft!
      validate!
      body = @govspeak_path.read(encoding: "UTF-8")
      html = HtmlAttachment.new(title: @manifest["title"], attachable: @edition)
      html.build_govspeak_content(body: body)
      file = nil

      ActiveRecord::Base.transaction do
        html.save!(context: :user_input)
        if @pdf_path
          File.open(@pdf_path, "rb") do |handle|
            # The native accessible flag follows independent PDF/A and PDF/UA
            # validation, not the filename, MIME type or a publisher's guess.
            file = FileAttachment.new(title: @manifest["title"], attachable: @edition,
              accessible: true, attachment_data_attributes: { file: handle })
            file.save!(context: :user_input)
          end
        end
      end
      # Preserve the publisher's own change history; do not publish or
      # overwrite the issuing institution's edition metadata.
      Whitehall.edition_services.draft_updater(@edition).perform!
      ServiceListeners::AttachmentUpdater.call(attachment_data: file.attachment_data) if file

      {
        edition_id: @edition.id,
        native_html_attachment_id: html.id,
        native_file_attachment_id: file&.id,
        source_revision: @manifest["source_revision"],
        source_sha256: @manifest["source_sha256"],
        asset_manager_id: nil,
        asset_manager_status: file ? "awaiting_native_worker_readback" : "not_applicable",
        edition_state: @edition.state
      }
    end

    # Read back a document already assembled in Whitehall. Retains the
    # original Document, Edition, Attachment and Asset Manager identifiers.
    # Never re-uploads or changes the issuing editor's version history.
    def readback_existing!(html_attachment:, file_attachment:)
      reject!("Document read access denied") unless
        @authorizer.respond_to?(:call) && @authorizer.call(:see, @edition, @actor)
      reject!("HTML attachment belongs to another edition") unless
        html_attachment.attachable == @edition
      reject!("File attachment belongs to another edition") unless
        file_attachment.attachable == @edition
      reject!("HTML attachment title changed") unless
        html_attachment.title == @manifest["title"]
      reject!("File attachment title changed") unless
        file_attachment.title == @manifest["title"]
      reject!("HTML body does not match original Govspeak") unless
        html_attachment.body == @govspeak_path.read(encoding: "UTF-8")
      reject!("File format is not PDF") unless file_attachment.pdf?
      assets = asset_readback!(file_attachment)
      reject!("Asset Manager has not returned the document PDF") if assets.empty?
      {
        document_id: @edition.document_id,
        edition_id: @edition.id,
        html_attachment_id: html_attachment.id,
        file_attachment_id: file_attachment.id,
        asset_manager_ids: assets.map { |asset| asset[:id] },
        edition_state: @edition.state
      }
    end

    # This must be called after the native background worker confirms upload.
    # Asset identifiers belong to a potentially restricted draft. A direct
    # call must never bypass native read permissions or attachment ownership.
    def asset_readback!(file_attachment)
      reject!("Document read access denied") unless
        @authorizer.respond_to?(:call) && @authorizer.call(:see, @edition, @actor)
      reject!("File attachment belongs to another edition") unless
        file_attachment.is_a?(FileAttachment) && file_attachment.attachable == @edition
      reject!("File format is not PDF") unless file_attachment.pdf?
      data = file_attachment.attachment_data
      reject!("Attachment data missing") unless data
      reject!("Asset Manager upload not complete") unless data.all_asset_variants_uploaded?
      assets = data.assets.to_a
      reject!("Original asset absent") unless assets.any? { |x| x.variant.to_s == "original" }
      reject!("Asset Manager ID or filename missing") if assets.any? do |x|
        x.asset_manager_id.blank? || x.filename.blank?
      end
      assets.map { |x| { id: x.asset_manager_id, filename: x.filename } }
    end

    private

    def reject!(reason)
      raise Rejected, reason
    end
  end
end
