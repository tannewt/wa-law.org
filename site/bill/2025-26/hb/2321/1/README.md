[wa-law.org](/) > [bill](/bill/) > [2025-26](/bill/2025-26/) > [HB 2321](/bill/2025-26/hb/2321/) > [Original Bill](/bill/2025-26/hb/2321/1/)

# HB 2321 - 3D printer blocking tech.

[Source](http://lawfilesext.leg.wa.gov/biennium/2025-26/Pdf/Bills/House%20Bills/2321.pdf)

## Section 1
The definitions in this section apply throughout this chapter unless the context clearly requires otherwise.

1. "Attorney general" includes the attorney general and his or her designees.

2. "Equipped with blocking features" means a three-dimensional printer has integrated a software controls process that deploys a firearms blueprint detection algorithm, such that those features identify and reject print requests for firearms or illegal firearm parts with a high degree of reliability and cannot be overridden or otherwise defeated by a user with significant technical skill.

3. "Firearm" has the same meaning as in RCW 9.41.010.

4. "Firearms blueprint detection algorithm" means a software service that evaluates three-dimensional printing files, whether in the form of stereolithography (STL) files or other computer-aided design files or geometric code, to determine if they can be used to program a three-dimensional printer to produce a firearm or illegal firearm parts, and flag any such files to prevent their use to manufacture said firearm or illegal firearm parts.

5. "Illegal firearm parts" means an unfinished frame or receiver, as that term is defined in RCW 9.41.010, or any part designed and intended solely and exclusively for use in converting a weapon into a machine gun, as that term is defined in RCW 9.41.010.

6. "Software controls process" means a system designed to stop a three-dimensional printer from initiating any print job unless the underlying three-dimensional printing file has been evaluated by a firearms blueprints detection algorithm and determined not to be a printing file that would produce a firearm or illegal firearm parts.

7. "Three-dimensional printer" means (a) any machine capable of rendering a three-dimensional object from a digital design file using additive manufacturing or (b) any machine capable of making three-dimensional modifications to an object from a digital design file using subtractive manufacturing.

## Section 2
This chapter applies to persons that conduct business in Washington or produce products or services that are sold or otherwise transferred to residents of Washington.

## Section 3
1. After July 1, 2027, no person who manufactures, wholesales, or sells any three-dimensional printer may sell or otherwise transfer for consideration a three-dimensional printer in this state unless:

    a. The three-dimensional printer is equipped with blocking features that prevent the printer from printing firearms and illegal firearm parts; and

    b. The manufacturer of the printer has attested to the integration of blocking features pursuant to subsection (2) of this section. Blocking features must meet or exceed the standards provided in sections 6 and 7 of this act and any rules and regulations adopted under those sections.

2. To comply with the attestation requirement of subsection (1) of this section, before selling or otherwise transferring for consideration a three-dimensional printer, the manufacturer must submit to the attorney general an attestation under penalty of perjury that the manufacturer has equipped all makes and models of the three-dimensional printer sold or transferred in this state with blocking features that meet or exceed the blocking features standards provided in sections 6 and 7 of this act and any rules and regulations adopted under those sections.

3. The attorney general, in consultation with research institutions, government agencies, or any other organization the attorney general deems appropriate, shall adopt rules and regulations to establish standards for equipping a printer with the blocking features required by this section and for providing the attestation required by this section. The attorney general may adopt rules and regulations for any other processes the attorney general deems necessary to carry out the provisions of this chapter.

4. This section does not apply to three-dimensional printers manufactured for, and exclusively sold to, buyers with a valid federal firearms manufacturing license issued under 18 U.S.C. Sec. 923.

## Section 4
1. Every natural person who violates section 3 of this act shall, for a first offense, be guilty of a misdemeanor and, for a second or subsequent offense, be guilty of a class C felony.

2. Every corporation, trust, unincorporated association, or partnership that violates section 3 of this act shall be guilty of a class C felony, punishable by up to five years in prison and a fine of up to $15,000.

3. Every natural person who files an attestation under section 3 of this act containing materially false information, which he or she knows to be false, shall be guilty of perjury in the second degree under RCW 9A.72.030.

## Section 5
The legislature finds that the practices covered by this chapter are matters vitally affecting the public interest for the purpose of applying the consumer protection act, chapter 19.86 RCW. A violation of this chapter is not reasonable in relation to the development and preservation of business and is an unfair or deceptive act in trade or commerce and an unfair method of competition for the purpose of applying the consumer protection act, chapter 19.86 RCW.

## Section 6
1. For the purpose of this chapter, a software controls process satisfies the blocking features requirement only if it effectively rejects print requests for firearms or illegal firearm parts with a high degree of reliability, and if it prevents a user with significant technical skill from bypassing a digital firearm manufacturing code detection algorithm and thereby subverting the software controls process.

2. A software controls process may be integrated into a three-dimensional printer's function in any of the following design forms:

    a. Firmware design. Integration of a firearms blueprint detection algorithm directly into a three-dimensional printer's firmware, such that any geometric code received by the printer must be screened by the algorithm before the printer will proceed to print, and such that the printer will reject print jobs identified by the algorithm as directing the printer to print firearms or illegal firearm parts;

    b. Integrated preprint software design. Limitation of a three-dimensional printer's operation to accept geometric code for printing exclusively from a single slicer or other preprint software, which may be the manufacturer's proprietary software, and integration of a firearms blueprint detection algorithm into that preprint software, such that any stereolithography file or other computer-aided design file must be screened by the algorithm before the software will proceed to produce geometric code, and such that the software will not produce geometric code for files that are identified by the algorithm as directing the printer to print firearms or illegal firearm parts; or

    c. Handshake authentication design. Limitation of a three-dimensional printer's operation to accept geometric code for printing only from specified slicers or other preprint software, wherein the printer will require a digital watermark or other authentication tool verifying the identity of the preprint software, and only if that preprint software has integrated a firearms blueprint detection algorithm qualified by the attorney general under subsection (4) of this section, such that any stereolithography file or other computer-aided design file must be screened by the algorithm before the software will proceed to produce geometric code, and such that the software will not produce geometric code for files that are identified by the algorithm as directing the printer to print firearms or illegal firearm parts.

3. A software controls process may also be integrated into a three-dimensional printer's function using a different design form than those described in subsection (2) of this section, provided that the software controls process both rejects print requests for firearms or illegal firearm parts with a high degree of reliability and is no less resistant to being defeated by a user with significant technical skill than the design forms described in subsection (2) of this section.

4. The attorney general, in consultation with research institutions, government agencies, or any other organization the attorney general deems appropriate, may adopt any rules or regulations to further establish standards for software control processes.

## Section 7
1. For the purpose of this chapter, a firearms blueprint detection algorithm satisfies the blocking features requirement only if it has the capacity, to a high degree of reliability, to:

    a. Screen three-dimensional printing files, whether in the form of stereolithography files or other computer-aided design files or geometric code;

    b. Detect and identify any such files that can be used to program a three-dimensional printer to produce firearms or illegal firearm parts; and

    c. Flag any such disallowed files for rejection by a software controls process.

2. An algorithm must use, at a minimum, a database of disallowed firearms blueprint files that have been commonly downloaded or shared on public internet forums. The algorithm must have the capacity both to detect files in its database and to actively seek to detect modified versions of those files. The attorney general may by rule or regulation require that an algorithm evaluate print requests, at a minimum, against all files in the files database described in section 8 of this act. An algorithm does not need to produce a perfect success rate at detecting disallowed files to effectively serve in blocking technology but must meet the technical standards for detection and flagging of disallowed files that are set forth in rules or regulations adopted by the attorney general pursuant to this chapter.

3. The database of disallowed firearms blueprint files that an algorithm uses must be able to be regularly updated, to an extent and with a frequency to be determined by the attorney general by rule or regulation that accounts for the rate of innovation in commonly available disallowed files.

4. The attorney general, in consultation with research institutions, government agencies, or any other organization the attorney general deems appropriate, may adopt any rules or regulations to further establish standards for firearms blueprint detection algorithms, including rules and regulations requiring developers and users of such algorithms to update such algorithms if new technology is found to be substantially more effective.

## Section 8
1. By August 1, 2026, the attorney general shall create and maintain a database of firearms blueprint files and illegal firearm parts blueprint files, including, at a minimum, by conducting reasonable searches of public internet forums, and shall maintain and update the database at least once per year, including by adding newly discovered files that enable the three-dimensional printing of firearms or illegal firearm parts.

2. The attorney general may consult with other government agencies and research institutions in this state to create and maintain a database of firearms blueprint files and illegal firearm parts blueprint files.

## Section 10
If any provision of this act or its application to any person or circumstance is held invalid, the remainder of the act or the application of the provision to other persons or circumstances is not affected.
