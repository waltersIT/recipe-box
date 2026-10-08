import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

// Fill these in before launch. They appear throughout both documents.
/** The person or company that runs the site, as it should appear in a contract. */
const OPERATOR = '[Legal name of the operator]'
/** Where legal notices, privacy requests and copyright complaints go. */
const CONTACT_EMAIL = '[legal@your-domain.com]'
/** Mailing address for legal notices and DMCA counter-notices. */
const MAILING_ADDRESS = '[Street address, City, State ZIP, United States]'
/** The U.S. state whose law governs the Terms and whose courts hear disputes. */
const GOVERNING_STATE = '[State]'
const EFFECTIVE_DATE = 'September 27, 2026'

const SITE = 'Recipe Box'

function Email() {
  return <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id}>
      <h2>{title}</h2>
      {children}
    </section>
  )
}

function LegalShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="legal">
      <h1>{title}</h1>
      <p className="muted small">Effective {EFFECTIVE_DATE} · Last updated {EFFECTIVE_DATE}</p>
      {children}
      <p className="muted small legal-other">
        See also: <Link to="/terms">Terms of Service</Link> · <Link to="/privacy">Privacy Policy</Link>
      </p>
    </article>
  )
}

export function TermsPage() {
  return (
    <LegalShell title="Terms of Service">
      <div className="alert info">
        <strong>The short version.</strong> Recipes, photos and comments on {SITE} are posted by its members, not by
        us. <strong>Whoever publishes a recipe is solely responsible for it.</strong> We don't test, verify or
        endorse any recipe, nutrition figure or health statement, and we accept no liability for what happens when
        you cook, eat or serve one. Check every recipe yourself, especially for allergens and safe cooking
        temperatures. This summary is for convenience only; the full terms below control.
      </div>

      <Section id="acceptance" title="1. Agreement to these terms">
        <p>
          These Terms of Service ("Terms") are a binding agreement between you and {OPERATOR} ("{SITE}", "we", "us"
          or "our") and govern your use of the {SITE} website, API, bookmarklet and related services (together, the
          "Service"). By creating an account, checking the box at sign-up, or otherwise using the Service, you agree
          to these Terms and to our <Link to="/privacy">Privacy Policy</Link>. If you don't agree, don't use the
          Service.
        </p>
        <p>
          <strong>
            Section 19 contains a binding arbitration agreement and class action waiver that affect how disputes are
            resolved. Please read it.
          </strong>
        </p>
      </Section>

      <Section id="eligibility" title="2. Who can use the Service">
        <p>
          You must be at least 13 years old to use the Service. The Service is not directed to children under 13,
          and we do not knowingly collect personal information from them, consistent with the Children's Online
          Privacy Protection Act (COPPA, 15 U.S.C. §§ 6501–6506). If you are under 18, or under the age of
          majority where you live, you may use the Service only with the involvement and consent of a parent or
          legal guardian, who agrees to these Terms on your behalf and is responsible for your use.
        </p>
        <p>
          You may not use the Service if you are barred from doing so under the laws of the United States or any
          other applicable jurisdiction, including if you are located in a country subject to a U.S. government
          embargo or are on a U.S. government list of prohibited or restricted parties.
        </p>
      </Section>

      <Section id="accounts" title="3. Your account">
        <p>
          Reading recipes needs no account. Posting recipes, importing, commenting, liking and following do. You
          agree to give accurate information, keep your password confidential, and tell us promptly at <Email /> if
          you suspect unauthorized use. You are responsible for everything that happens under your account. Your
          username, display name, bio and photo are public. Don't choose a username that impersonates someone else,
          infringes a trademark, or is offensive.
        </p>
      </Section>

      <Section id="content" title="4. Content you post">
        <p>
          "User Content" means anything you submit to the Service: recipes, ingredient lists, instructions, notes,
          nutrition information, tags, ratings, photos, imported web pages, PDFs and screenshots, comments, replies
          and profile information.
        </p>
        <p>
          <strong>You own your User Content, and you are solely responsible for it.</strong> By posting it, you
          represent and warrant that: (a) you own it or have every right, license and permission needed to post it
          and to grant the license below; (b) it is accurate and not misleading, to the best of your knowledge; (c)
          it doesn't infringe or violate anyone's copyright, trademark, privacy, publicity or other rights; and (d)
          it complies with these Terms and all applicable laws.
        </p>
        <p>
          You grant us a worldwide, non-exclusive, royalty-free, sublicensable and transferable license to host,
          store, reproduce, display, publicly perform, format, adapt (for example, resizing images or converting file
          formats) and distribute your User Content in connection with operating, providing, promoting and improving
          the Service. This license ends when you delete the content or your account, except for: copies kept in
          backups for a limited time; comments you left on other people's recipes, which remain after you delete your
          account, with your name, username and photo removed and shown as "[deleted]", unless you delete them first;
          content others have quoted; and anything we must keep to comply with law or resolve disputes.
        </p>
        <p>
          We do not claim ownership of your User Content and we are not obliged to host, display or keep any of it.
          We may, but are not required to, review, edit for formatting, refuse, or remove User Content at any time
          and for any reason, including if we believe it violates these Terms or the law.
        </p>
      </Section>

      <Section id="no-liability" title="5. No liability for recipes: the publisher is responsible">
        <p className="legal-emphasis">
          ALL RECIPES AND RELATED CONTENT ON THE SERVICE ARE PUBLISHED BY USERS, NOT BY {SITE.toUpperCase()}. THE
          PERSON WHO PUBLISHES A RECIPE IS SOLELY AND ENTIRELY RESPONSIBLE FOR IT, INCLUDING ITS INGREDIENTS,
          INSTRUCTIONS, QUANTITIES, COOKING TIMES AND TEMPERATURES, ALLERGEN INFORMATION, NUTRITION INFORMATION,
          HEALTH OR DIETARY STATEMENTS, PHOTOS AND SOURCE ATTRIBUTION. TO THE FULLEST EXTENT PERMITTED BY LAW,{' '}
          {SITE.toUpperCase()} AND {OPERATOR.toUpperCase()} HAVE NO LIABILITY WHATSOEVER FOR ANY RECIPE OR OTHER USER
          CONTENT, OR FOR ANY ILLNESS, ALLERGIC REACTION, INJURY, DEATH, PROPERTY DAMAGE OR OTHER LOSS ARISING FROM
          PREPARING, COOKING, SERVING, EATING, SELLING OR OTHERWISE RELYING ON IT.
        </p>
        <p>In particular, we do not:</p>
        <ul>
          <li>create, test, verify, review, approve or endorse any recipe;</li>
          <li>check that ingredients, quantities, times or temperatures are correct or safe;</li>
          <li>check recipes for allergens or confirm that a recipe is suitable for any diet or condition;</li>
          <li>verify nutrition figures or any health, diet or wellness statement;</li>
          <li>verify that the publisher has the right to share a recipe or photo.</li>
        </ul>
        <p>
          We are an interactive computer service that hosts content provided by others. Under Section 230 of the
          Communications Decency Act (47 U.S.C. § 230), we are not the publisher or speaker of User Content, and
          removing or choosing not to remove content does not make us responsible for it.
        </p>
        <p>
          <strong>Cooking involves real risks</strong>, including from knives, heat, open flame, hot oil, pressure
          cookers, raw or undercooked food, foodborne illness, food allergies and intolerances, and wild or foraged
          ingredients. You use recipes from the Service voluntarily and at your own risk, and you assume all of
          those risks. Use your own judgment, and when in doubt, don't make it.
        </p>
      </Section>

      <Section id="food-safety" title="6. Food safety, FDA and health notices">
        <p>
          <strong>Not evaluated by the FDA.</strong> No recipe, nutrition figure or statement on the Service has
          been reviewed, evaluated or approved by the U.S. Food and Drug Administration (FDA), the U.S. Department of
          Agriculture (USDA) or any other government agency. Any statement about health, disease, weight or wellness
          made in User Content is the publisher's own and is not intended to diagnose, treat, cure or prevent any
          disease.
        </p>
        <p>
          <strong>Not medical or dietary advice.</strong> Nothing on the Service is medical, nutritional or dietary
          advice. Talk to a doctor, registered dietitian or other qualified professional before changing your diet,
          especially if you are pregnant or nursing, have a food allergy, diabetes, celiac disease, kidney disease
          or another medical condition, take medication, or are cooking for infants, young children, older adults or
          people with weakened immune systems.
        </p>
        <p>
          <strong>Nutrition information is an unverified estimate.</strong> Nutrition values are entered by
          publishers or extracted automatically from their sources. They are not a Nutrition Facts label under FDA
          regulations (21 C.F.R. § 101.9), may be incomplete or wrong, and change with brands, substitutions and
          portion sizes.
        </p>
        <p>
          <strong>Check for allergens yourself.</strong> Recipes may contain, or be cross-contaminated with, any of
          the major food allergens identified under the Food Allergen Labeling and Consumer Protection Act (FALCPA)
          and the FASTER Act of 2021: milk, eggs, fish, crustacean shellfish, tree nuts, peanuts, wheat, soybeans
          and sesame, as well as other allergens. Read every ingredient, and every product label, yourself. Allergen
          lists and "free-from" tags on the Service are user-supplied and not guaranteed.
        </p>
        <p>
          <strong>Cook food safely.</strong> Consuming raw or undercooked meats, poultry, seafood, shellfish or eggs
          may increase your risk of foodborne illness, especially if you have certain medical conditions. Follow the
          safe minimum internal temperatures and handling guidance published at{' '}
          <a href="https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures" target="_blank" rel="noreferrer">
            FoodSafety.gov
          </a>
          , even if a recipe says otherwise. Home canning, curing, fermenting, infusing oils and garlic, and
          preparing wild mushrooms or foraged plants carry special risks, including botulism and poisoning; rely only
          on tested methods from authoritative sources such as the USDA and the National Center for Home Food
          Preservation.
        </p>
        <p>
          <strong>Alcohol.</strong> Some recipes contain alcohol. Only people of legal drinking age (21 in the United
          States) should prepare or consume them. Don't drink and drive.
        </p>
        <p>
          <strong>Selling food.</strong> {SITE} is not a food manufacturer, processor, retailer or food facility and
          is not registered with the FDA. If you make food from a recipe to sell, donate or serve to the public, you
          alone are responsible for complying with all applicable laws, including the Federal Food, Drug, and
          Cosmetic Act, FDA and USDA regulations, the FDA Food Code as adopted where you are, food labeling and
          allergen disclosure requirements, and state and local cottage food, licensing and health department rules.
        </p>
      </Section>

      <Section id="acceptable-use" title="7. Rules for using the Service">
        <p>You agree not to post content, or use the Service in a way, that:</p>
        <ul>
          <li>infringes anyone's copyright, trademark, privacy, publicity or other rights;</li>
          <li>
            is knowingly dangerous or intended to cause harm, including recipes with intentionally unsafe
            instructions, toxic substances presented as food, or dangerous "challenges";
          </li>
          <li>
            involves making, using or distributing substances that are illegal under U.S. federal law, including
            controlled substances;
          </li>
          <li>
            makes claims that a food or recipe can diagnose, treat, cure or prevent a disease, or promotes or sells
            drugs, dietary supplements or products with unapproved health claims;
          </li>
          <li>
            is false, misleading or deceptive, including sponsored or paid content without the clear disclosure
            required by the FTC's Endorsement Guides (16 C.F.R. Part 255);
          </li>
          <li>
            is unlawful, defamatory, obscene, harassing, hateful, threatening, sexually explicit, or exploits or
            endangers minors;
          </li>
          <li>shares anyone else's personal information without their permission;</li>
          <li>impersonates anyone or misrepresents your affiliation with anyone;</li>
          <li>is spam, advertising, chain letters, or links to malware or phishing;</li>
          <li>
            tries to access accounts or data that aren't yours, probes or breaches our security, or interferes with
            or overloads the Service;
          </li>
          <li>
            scrapes, crawls or harvests the Service or its users' data by automated means, except as allowed by our
            robots.txt, or uses the Service to build a competing database;
          </li>
          <li>uses the Service to break any law or to help anyone else break these rules.</li>
        </ul>
        <p>
          Comments are visible to everyone. Their author can edit or delete them, and a recipe's publisher can
          remove comments left on their recipe. We may remove any content and suspend or terminate any account that
          breaks these rules.
        </p>
      </Section>

      <Section id="imports" title="8. Importing recipes and automated processing">
        <p>
          The Service can import recipes from web links, the bookmarklet, PDFs and images. When you import
          something, you are the one choosing to copy and publish it, and you are responsible for having the right
          to do so and for complying with the source website's terms. Lists of ingredients are generally not
          protected by copyright, but a recipe's descriptive text, instructions, stories and photos often are. When
          in doubt, rewrite the instructions in your own words, use your own photos, and credit the source.
        </p>
        <p>
          Imports may be processed automatically, including by optical character recognition and by an artificial
          intelligence model provided by a third party (see our <Link to="/privacy">Privacy Policy</Link>).
          Automated extraction can make mistakes, such as wrong quantities, units, temperatures or missing
          ingredients. Every import opens in the editor so you can check it; you are responsible for reviewing and
          correcting it before you publish.
        </p>
      </Section>

      <Section id="copyright" title="9. Copyright complaints (DMCA)">
        <p>
          We respect intellectual property rights and respond to notices of alleged infringement under the Digital
          Millennium Copyright Act (17 U.S.C. § 512). If you believe content on the Service infringes your
          copyright, send a written notice to our designated agent that includes:
        </p>
        <ol>
          <li>your physical or electronic signature;</li>
          <li>identification of the copyrighted work you claim is infringed;</li>
          <li>identification of the infringing material and its location on the Service (such as the page URL);</li>
          <li>your name, address, telephone number and email address;</li>
          <li>
            a statement that you have a good faith belief that the use is not authorized by the copyright owner, its
            agent or the law; and
          </li>
          <li>
            a statement, under penalty of perjury, that the information in your notice is accurate and that you are
            the copyright owner or authorized to act on the owner's behalf.
          </li>
        </ol>
        <p>
          Designated agent: {OPERATOR}, Attn: Copyright Agent, {MAILING_ADDRESS}, <Email />.
        </p>
        <p>
          If your content was removed and you believe that was a mistake or misidentification, you may send a
          counter-notice as described in 17 U.S.C. § 512(g)(3). Knowingly false notices or counter-notices may make
          you liable for damages under 17 U.S.C. § 512(f). We will terminate, in appropriate circumstances, the
          accounts of users who are repeat infringers.
        </p>
      </Section>

      <Section id="our-rights" title="10. Our intellectual property">
        <p>
          The Service itself, including its software, design, logos and the "{SITE}" name, belongs to us or our
          licensors and is protected by law. Except for your User Content and the license we grant you to use the
          Service under these Terms, you get no rights in it. If you send us feedback or suggestions, we may use
          them without any obligation to you.
        </p>
      </Section>

      <Section id="third-parties" title="11. Third-party sites and services">
        <p>
          Recipes may link to, or be imported from, websites and services we don't control. We are not responsible
          for their content, accuracy, availability, products or privacy practices, and a link doesn't mean we
          endorse them. Your use of them is governed by their own terms.
        </p>
      </Section>

      <Section id="disclaimer" title="12. Disclaimer of warranties">
        <p className="legal-emphasis">
          THE SERVICE AND ALL CONTENT ON IT ARE PROVIDED "AS IS" AND "AS AVAILABLE", WITHOUT WARRANTIES OF ANY KIND,
          EXPRESS, IMPLIED OR STATUTORY. TO THE FULLEST EXTENT PERMITTED BY LAW, WE DISCLAIM ALL WARRANTIES,
          INCLUDING IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, NON-INFRINGEMENT,
          ACCURACY AND QUIET ENJOYMENT, AND ANY WARRANTIES ARISING FROM COURSE OF DEALING OR USAGE OF TRADE. WE DO
          NOT WARRANT THAT ANY RECIPE IS SAFE, ACCURATE, COMPLETE, SUITABLE FOR YOUR DIET OR FREE OF ALLERGENS, OR
          THAT THE SERVICE WILL BE UNINTERRUPTED, SECURE, ERROR-FREE OR FREE OF VIRUSES, OR THAT CONTENT WILL BE
          PRESERVED WITHOUT LOSS. KEEP YOUR OWN COPIES OF ANYTHING IMPORTANT TO YOU.
        </p>
      </Section>

      <Section id="limitation" title="13. Limitation of liability">
        <p className="legal-emphasis">
          TO THE FULLEST EXTENT PERMITTED BY LAW, IN NO EVENT WILL {OPERATOR.toUpperCase()}, {SITE.toUpperCase()}, OR
          OUR OWNERS, OFFICERS, EMPLOYEES, CONTRACTORS, AGENTS, LICENSORS OR SERVICE PROVIDERS BE LIABLE FOR ANY
          INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY OR PUNITIVE DAMAGES, OR FOR ANY PERSONAL INJURY,
          ILLNESS, DEATH, PROPERTY DAMAGE, OR LOSS OF PROFITS, DATA, GOODWILL OR USE, ARISING OUT OF OR RELATING TO
          THE SERVICE, ANY RECIPE OR OTHER USER CONTENT, OR THE CONDUCT OF ANY USER OR THIRD PARTY, WHETHER BASED ON
          CONTRACT, TORT (INCLUDING NEGLIGENCE), STRICT LIABILITY, PRODUCT LIABILITY OR ANY OTHER THEORY, EVEN IF WE
          HAVE BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
        </p>
        <p className="legal-emphasis">
          THE SERVICE IS PROVIDED FREE OF CHARGE. TO THE FULLEST EXTENT PERMITTED BY LAW, OUR TOTAL LIABILITY FOR ALL
          CLAIMS RELATING TO THE SERVICE WILL NOT EXCEED THE AMOUNT YOU PAID US TO USE THE SERVICE IN THE 12 MONTHS
          BEFORE THE CLAIM AROSE.
        </p>
        <p>
          Some jurisdictions do not allow the exclusion or limitation of certain warranties or damages, so some of
          the above may not apply to you. In that case, our liability is limited to the smallest extent the law
          allows. Nothing in these Terms limits liability that cannot be limited by law.
        </p>
      </Section>

      <Section id="indemnity" title="14. Indemnification">
        <p>
          You agree to defend, indemnify and hold harmless {OPERATOR} and our owners, officers, employees,
          contractors and agents from and against any claims, liabilities, damages, losses, judgments, fines and
          expenses, including reasonable attorneys' fees, arising out of or related to: (a) your User Content,
          including any recipe you publish and any illness, allergic reaction, injury or loss anyone claims it
          caused; (b) your use of the Service; (c) your violation of these Terms; or (d) your violation of any law or
          anyone else's rights. We may take over the defense of any such claim, and you agree to cooperate with us.
        </p>
      </Section>

      <Section id="termination" title="15. Suspension and termination">
        <p>
          You may stop using the Service at any time and may delete your account yourself at any time from your
          profile (Edit profile → Delete account), or by emailing <Email />.
          We may suspend or terminate your access, or remove your content, at any time, with or without notice, if we
          believe you have broken these Terms or the law, to protect the Service or other users, or if we stop
          offering the Service. Sections 4 (license survival terms), 5, 6, 9, 10 and 12 through 21 survive
          termination.
        </p>
      </Section>

      <Section id="changes" title="16. Changes to the Service and these Terms">
        <p>
          We may change, suspend or discontinue any part of the Service at any time. We may update these Terms; when
          we do, we'll change the "Last updated" date above, and for material changes we'll give reasonable notice,
          such as a notice on the site. Changes take effect when posted unless we say otherwise. If you keep using
          the Service after they take effect, you accept the updated Terms. Changes to Section 19 won't apply to
          disputes that arose before the change.
        </p>
      </Section>

      <Section id="electronic" title="17. Electronic communications">
        <p>
          You consent to receive communications from us electronically, such as through the Service or by email,
          and agree that these electronic communications satisfy any legal requirement that they be in writing,
          consistent with the federal Electronic Signatures in Global and National Commerce Act (E-SIGN Act). Your
          agreement to these Terms by checking a box or using the Service has the same effect as a signature.
        </p>
      </Section>

      <Section id="law" title="18. Governing law and venue">
        <p>
          These Terms and any dispute relating to them or the Service are governed by the Federal Arbitration Act,
          applicable U.S. federal law, and the laws of the State of {GOVERNING_STATE}, without regard to its
          conflict-of-laws rules. Subject to Section 19, any claim not subject to arbitration must be brought
          exclusively in the state or federal courts located in the State of {GOVERNING_STATE}, and you and we
          consent to their personal jurisdiction.
        </p>
      </Section>

      <Section id="arbitration" title="19. Dispute resolution, arbitration and class action waiver">
        <p>
          <strong>Informal resolution first.</strong> Before filing any claim, you and we agree to try to resolve the
          dispute informally for at least 60 days, starting when one side sends the other a written notice
          describing the dispute (to us at <Email />).
        </p>
        <p>
          <strong>Binding individual arbitration.</strong> If it isn't resolved informally, you and we agree that
          any dispute arising out of or relating to these Terms or the Service will be resolved by binding
          individual arbitration administered by the American Arbitration Association under its Consumer Arbitration
          Rules, rather than in court. Either party may instead bring an individual claim in small claims court if it
          qualifies, and either party may seek an injunction in court for infringement or misuse of intellectual
          property. The arbitrator, not a court, decides questions of arbitrability, except that a court decides the
          enforceability of the class action waiver below.
        </p>
        <p>
          <strong>Class action waiver.</strong> YOU AND WE AGREE THAT EACH MAY BRING CLAIMS AGAINST THE OTHER ONLY IN
          AN INDIVIDUAL CAPACITY, AND NOT AS A PLAINTIFF OR CLASS MEMBER IN ANY PURPORTED CLASS, COLLECTIVE,
          CONSOLIDATED OR REPRESENTATIVE PROCEEDING. YOU AND WE WAIVE ANY RIGHT TO A JURY TRIAL.
        </p>
        <p>
          <strong>Opting out.</strong> You may opt out of this arbitration agreement by emailing <Email /> within 30
          days of first agreeing to these Terms, with your username and a statement that you opt out of arbitration.
          Opting out does not affect any other part of these Terms.
        </p>
        <p>
          <strong>Time limit.</strong> To the extent permitted by law, any claim must be brought within one year after
          it arose, or it is permanently barred.
        </p>
      </Section>

      <Section id="california" title="20. Notice for California users">
        <p>
          Under California Civil Code § 1789.3, California users are entitled to this notice: the Service is
          provided by {OPERATOR}, {MAILING_ADDRESS}. The Service is free. You may contact the Complaint Assistance
          Unit of the Division of Consumer Services of the California Department of Consumer Affairs in writing at
          1625 North Market Blvd., Suite N 112, Sacramento, CA 95834, or by telephone at (800) 952-5210.
        </p>
      </Section>

      <Section id="general" title="21. General">
        <p>
          These Terms and the Privacy Policy are the entire agreement between you and us about the Service. If any
          part of these Terms is found unenforceable, that part will be enforced to the maximum extent permissible
          and the rest will remain in effect. Our failure to enforce any right is not a waiver of it. You may not
          assign these Terms without our written consent; we may assign them, including in a merger, acquisition or
          sale of assets. Nothing in these Terms creates any partnership, joint venture, employment or agency
          relationship. Section headings are for convenience only.
        </p>
        <p>
          Questions about these Terms? Contact {OPERATOR} at <Email /> or {MAILING_ADDRESS}.
        </p>
      </Section>
    </LegalShell>
  )
}

export function PrivacyPage() {
  return (
    <LegalShell title="Privacy Policy">
      <div className="alert info">
        <strong>The short version.</strong> We collect what you give us to run your account and show your recipes,
        plus the basic technical data every website receives. Your profile, recipes and comments are public. We don't
        sell or share your personal information for advertising, we don't run ads or third-party trackers, and the
        only cookies we set are the ones needed to keep you signed in and secure.
      </div>

      <Section id="scope" title="1. Who we are and what this covers">
        <p>
          This Privacy Policy explains how {OPERATOR} ("{SITE}", "we", "us") collects, uses, discloses and protects
          personal information when you use the {SITE} website, API and bookmarklet (the "Service"). It is part of
          our <Link to="/terms">Terms of Service</Link>. Contact us at <Email /> or {MAILING_ADDRESS}.
        </p>
      </Section>

      <Section id="collect" title="2. Information we collect">
        <h3>Information you give us</h3>
        <ul>
          <li>
            <strong>Account information:</strong> username, password (stored only as a salted, one-way hash; we
            never see or store it in readable form), email address if you provide one, and the date and time you
            agreed to our Terms and this Policy.
          </li>
          <li>
            <strong>Profile information:</strong> display name, bio and profile photo.
          </li>
          <li>
            <strong>Content:</strong> recipes, photos, tags, ratings, notes and nutrition information you enter, and
            the original files you import (PDFs, screenshots, photos and web pages), plus comments and replies.
          </li>
          <li>
            <strong>Activity:</strong> recipes you like, people you follow, and people who follow you.
          </li>
          <li>
            <strong>Communications:</strong> anything you send us, such as support, privacy or copyright requests.
          </li>
        </ul>
        <h3>Information collected automatically</h3>
        <ul>
          <li>
            <strong>Technical and log data:</strong> your IP address, browser and device type, the pages and API
            addresses requested, referring page, and date and time, which our web servers record in standard logs.
          </li>
          <li>
            <strong>Session data:</strong> to count each recipe view once per visit, we remember in your session which
            recipes you've recently viewed. View counts are shown only as totals.
          </li>
        </ul>
        <h3>File metadata</h3>
        <p>
          Photos and files can contain hidden metadata, such as the date taken, camera model and, for some phone
          photos, the GPS location. Uploaded photos and original import files may be stored with that metadata and
          may be downloadable by others. Remove location data from photos before uploading them if you don't want to
          share it.
        </p>
        <p>We do not collect sensitive information such as government IDs, financial account or payment data.</p>
      </Section>

      <Section id="cookies" title="3. Cookies and tracking">
        <p>
          We use only cookies that are strictly necessary for the Service to work: a session cookie that keeps you
          signed in and remembers recent views, and a security cookie that protects forms against cross-site request
          forgery. We do not use advertising cookies, analytics services, social media pixels, or other third-party
          trackers, and we do not track you across other websites. Because we don't engage in cross-site tracking,
          we don't change our practices in response to "Do Not Track" signals; we also treat Global Privacy Control
          signals as a valid opt-out of sale and sharing, which we don't do in any case.
        </p>
        <p>
          The bookmarklet runs only when you click it. It sends us the address and content of the page you're on so
          it can be imported into your account.
        </p>
      </Section>

      <Section id="use" title="4. How we use information">
        <ul>
          <li>to create and run your account and sign you in;</li>
          <li>to publish and display your recipes, profile, comments, likes and follows;</li>
          <li>to import recipes from the links and files you provide;</li>
          <li>to build your feed and rank popular recipes;</li>
          <li>to keep the Service secure, prevent abuse and spam, and debug problems;</li>
          <li>to respond to your requests and send you service-related messages;</li>
          <li>
            to enforce our Terms, respond to copyright notices, and comply with legal obligations and lawful requests;
          </li>
          <li>to improve the Service.</li>
        </ul>
        <p>
          We don't use your information for targeted advertising, and we don't make decisions about you based solely
          on automated processing that have legal or similarly significant effects. We don't send marketing email; if
          we ever do, it will comply with the CAN-SPAM Act and include a way to unsubscribe.
        </p>
      </Section>

      <Section id="public" title="5. What's public">
        <p>
          Anyone, with or without an account, can see your username, display name, bio, profile photo, the recipes
          you've published (including their photos and original import files), your comments and replies, who you
          follow and who follows you, and like and view counts. Search engines may index public pages, and others may
          copy public content. Don't post anything you want to keep private.
        </p>
      </Section>

      <Section id="share" title="6. How we share information">
        <p>
          <strong>We do not sell your personal information, and we do not "share" it for cross-context behavioral
          advertising</strong> as those terms are defined under the California Consumer Privacy Act and similar
          state laws. We disclose personal information only:
        </p>
        <ul>
          <li>
            <strong>With service providers</strong> that process it on our behalf under contract, including Amazon
            Web Services (hosting, database and storage in the United States) and, when automated import is enabled,
            Anthropic, which provides the AI model that reads PDFs, screenshots and web pages you import. Files and
            page text you import may be sent to Anthropic for processing; see{' '}
            <a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noreferrer">
              Anthropic's privacy policy
            </a>
            .
          </li>
          <li>
            <strong>For legal reasons:</strong> when we believe in good faith it is required by law, subpoena, court
            order or other legal process, or necessary to protect the rights, property or safety of {SITE}, our users
            or the public, including to investigate fraud, abuse or security issues.
          </li>
          <li>
            <strong>In a business transfer:</strong> as part of a merger, acquisition, financing, reorganization, or
            sale of all or part of our assets, subject to this Policy.
          </li>
          <li>
            <strong>With your direction or consent</strong>, and as public content described above.
          </li>
        </ul>
      </Section>

      <Section id="retention" title="7. How long we keep information">
        <p>
          We keep account information and content for as long as your account is active. When you delete a recipe,
          comment or photo, it is removed from the Service. When you delete your account (Edit profile → Delete
          account), your account, profile, recipes with their photos and files, likes and follows are deleted
          immediately and permanently. Comments you left on other people's recipes remain so the conversation still
          makes sense, but your name, username and photo are removed from them and they're shown as "[deleted]".
          Delete any comment you don't want kept before deleting your account. If you ask us by email instead, we
          do the same within 45 days. Copies in backups are overwritten on a rolling basis, and we may keep information we
          must keep to comply with law, resolve disputes, prevent abuse or enforce our Terms. Server logs are kept only as long as needed for security and troubleshooting.
        </p>
      </Section>

      <Section id="security" title="8. Security">
        <p>
          We use reasonable administrative, technical and physical safeguards, including encrypted connections
          (HTTPS), hashed passwords, and access controls on our servers and database. No method of transmission or
          storage is completely secure, so we can't guarantee absolute security. If a breach of security affects your
          personal information, we will notify you and the authorities as required by applicable law.
        </p>
      </Section>

      <Section id="children" title="9. Children's privacy">
        <p>
          The Service is not directed to children under 13, and we do not knowingly collect personal information from
          them, in compliance with the Children's Online Privacy Protection Act (COPPA). Everyone who signs up
          confirms they are at least 13. If we learn we've collected personal information from a child under 13, we
          will delete it promptly. If you believe a child under 13 has given us information, contact us at <Email />.
        </p>
      </Section>

      <Section id="rights" title="10. Your choices and rights">
        <p>
          You can view and update your profile, and edit or delete your recipes and comments, at any time in the
          Service. You can delete your account yourself at any time from your profile (Edit profile → Delete
          account), or ask us to by emailing <Email />. Comments you left on other people's recipes stay after
          account deletion, without your name, as described in Section 7.
        </p>
        <p>
          Depending on where you live, including California, Colorado, Connecticut, Delaware, Indiana, Iowa,
          Kentucky, Maryland, Minnesota, Montana, Nebraska, New Hampshire, New Jersey, Oregon, Rhode Island,
          Tennessee, Texas, Utah, Virginia and other states with comprehensive privacy laws, you may have the right
          to:
        </p>
        <ul>
          <li>know or access the personal information we have about you and how we use and disclose it;</li>
          <li>receive a copy of it in a portable format;</li>
          <li>correct inaccurate personal information;</li>
          <li>delete personal information;</li>
          <li>
            opt out of the sale or sharing of personal information, targeted advertising, and certain profiling (we
            don't do any of these);
          </li>
          <li>limit the use of sensitive personal information (we don't collect any); and</li>
          <li>not be discriminated against for exercising these rights.</li>
        </ul>
        <p>
          To make a request, email <Email /> from the email address on your account, or tell us your username. We
          will verify your request by confirming you control the account, and we respond within the time required by
          law (generally 45 days). You may use an authorized agent, who must provide proof of your permission. If we
          deny your request, you may appeal by replying to our decision; if we deny your appeal, you can contact your
          state attorney general.
        </p>
        <p>
          <strong>California "Shine the Light":</strong> we do not disclose personal information to third parties
          for their own direct marketing purposes.
        </p>
        <p>
          <strong>Categories under California law:</strong> in the last 12 months we have collected identifiers
          (username, email, IP address), customer records (display name, bio), internet or network activity
          (logs, likes, follows, views), and audio/visual information (photos you upload). We collect them from you and your device for the purposes in Section 4 and disclose
          them only to the recipients in Section 6. We do not sell or share them.
        </p>
      </Section>

      <Section id="international" title="11. Users outside the United States">
        <p>
          The Service is operated in and hosted in the United States, and your information will be processed there,
          where data protection laws may differ from those in your country. If you are in the European Economic Area,
          the United Kingdom or Switzerland, we process your personal information to perform our contract with you
          (running your account and publishing your content), for our legitimate interests (keeping the Service
          secure and improving it), to comply with legal obligations, and with your consent where required. You have
          the rights to access, correct, delete, restrict or object to processing, to data portability, to withdraw
          consent at any time, and to lodge a complaint with your local data protection authority. Contact us at{' '}
          <Email /> to exercise them.
        </p>
      </Section>

      <Section id="changes" title="12. Changes to this Policy">
        <p>
          We may update this Privacy Policy from time to time. We'll change the "Last updated" date above and, for
          material changes, give reasonable notice, such as a notice on the site, before they take effect. We won't
          use previously collected personal information in a materially different way without your consent where the
          law requires it.
        </p>
      </Section>

      <Section id="contact" title="13. Contact us">
        <p>
          {OPERATOR}
          <br />
          {MAILING_ADDRESS}
          <br />
          <Email />
        </p>
      </Section>
    </LegalShell>
  )
}
