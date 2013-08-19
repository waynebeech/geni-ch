#----------------------------------------------------------------------
# Copyright (c) 2011-2013 Raytheon BBN Technologies
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and/or hardware specification (the "Work") to
# deal in the Work without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Work, and to permit persons to whom the Work
# is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Work.
#
# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS
# IN THE WORK.
#----------------------------------------------------------------------

import optparse
import os, sys
import sfa.trust.certificate
from ABACManager import ABACManager

# Pull the certificate from the speaks-for credential
def get_cert_from_credential(cred):
    start_tag = '<X509Certificate>'
    end_tag = '</X509Certificate>'
    start_index = cred.find(start_tag)
    end_index = cred.find(end_tag)
    raw_cert = cred[start_index+len(start_tag):end_index]
    cert_string = '-----BEGIN CERTIFICATE-----\n%s\n-----END CERTIFICATE-----' % raw_cert
    return cert_string

# Pull out the URN from the certificate
def get_urn_from_cert(cert):
    cert_object = sfa.trust.certificate.Certificate(string=cert)
    subject_alt_names = cert_object.get_extension('subjectAltName')
    san_parts = subject_alt_names.split(',')
    urn = None
    for san_part in san_parts:
        san_part = san_part.strip()
        if san_part.startswith('URI:urn:publicid'):
            urn = san_part[4:]
            break
    return urn

# Determine if the given method context is 'speaks-for'
# That is:
#     1. There is a 'speaking_for' option with the value of the 
#          URN of the spoken-for user
#     2. There is a speaks-for credential in the list of credentials 
#         that is signed by the spoken-for user authorizing the 
#         speaking entity to speak for it
#     3. The URN of the 'speaking_for' option matches the URN 
#         in the speaks-for credential
#     4. The certificate of the spoken-for user is in the 
#         list of credentials [Note: This one is still open to debate...]
#
# Args:
#   client_cert: the cert of the actual invoker of the SSL connection
#   credentials: the list of credentials passed with the call, 
#        possibly including user certs and speaks-for credentials
#   options: the dictionary of options supplied with the call, 
#        possibly including a 'speaking_for' option
#
# Return: 
#   agent_cert: Cert of actual (spoken for) speaker if 'speaks for', 
#        client_cert if not.
#   revised_options : Original options with 
#       {'speaking-as' : original_client_cert} added if 'speaks for'
def determine_speaks_for(client_cert, credentials, options): 
    revised_options = dict(options) # Make a copy of original options
    agent_cert = client_cert
    client_urn = get_urn_from_cert(client_cert)

    # Pull out speaks_for credential
    speaks_for_credential = None
    for credential in credentials:
        if credential['geni_type'] == 'ABAC' and \
                credential['geni_value'].find('speaks_for') >= 0:
            speaks_for_credential = credential['geni_value']
            break

    # Pull out speaking_for option
    speaking_for = None
    if options.has_key('speaking_for'):
        speaking_for = options['speaking_for']

    # Check arguments:

    # If neither a speaks-for credential or a speaking_for option, this is not speaks-for.
    # Return the cert and options as given
    if not speaks_for_credential and not speaking_for:
        return client_cert, options

    # If there is either a  speaks-for credential or a speaking_for option, 
    #    but not both, error
    if (speaks_for_credential and not speaking_for) or \
            (not speaks_for_credential and speaking_for):
        raise Exception("Must have both speaks-for-credential and speaking_for option")

    # We are processing aspeaks-for request

    # Get the agent_cert
    agent_cert = get_cert_from_credential(speaks_for_credential)

    # Get the agent_urn
    agent_urn = get_urn_from_cert(agent_cert)
    
    # The agent_urn must match the speaking_for option
    if agent_urn != speaking_for:
        raise Exception("Mismatch: speaking_for %s and agent URN %s" % (speaking_for, agent_urn))

    # The speaks-for credential must assert the statement AGENT.speaks_for(AGENT)<-CLIENT
    certs_by_name = {"CLIENT" : client_cert, "AGENT" : agent_cert}
    query = "AGENT.speaks_for(AGENT)<-CLIENT"
    abac_manager = ABACManager(certs_by_name = certs_by_name, raw_assertions=[speaks_for_credential])
    ok, proof = abac_manager.query(query)
    if not ok:
        raise Exception("Speaks-For credential does not assert that agent allows client to speak for agent")

    # Update options
    revised_options['speaking_as'] = client_urn

    return agent_cert, revised_options

def parseOptions():
    parser = optparse.OptionParser()

    home = os.getenv('HOME')
    gcf_home = os.path.join(home, '.gcf')

    parser.add_option("--speaks_for_cred", \
                          help="Location of speaks-for credential", \
                          default=None)
    parser.add_option("--speaker_cert", help="Location of speaker cert", \
                          default=os.path.join(gcf_home, 'alice-cert.pem'))
    parser.add_option("--agent_cert", help="Location of spoken-for cert", \
                          default=None)
    parser.add_option("--agent_urn", help="URN of (spoken-for) agent", \
                          default=None)

    [opts, args] = parser.parse_args(sys.argv)
    return opts, args


if __name__ == "__main__":

    opts, args = parseOptions()

    options = {}
    client_cert = open(opts.speaker_cert).read()
    credentials = []
    if opts.speaks_for_cred:
        filename = opts.speaks_for_cred
        sf_cred = open(filename).read()
        credentials.append({'geni_type' : 'ABAC', 'geni_value' : sf_cred, 'geni_version' : '1'})

    # Set agent_urn
    agent_urn = None
    if opts.agent_urn:
        agent_urn = opts.agent_urn
    if opts.agent_cert:
        agent_cert = open(opts.agent_cert).read()
        agent_urn = get_urn_from_cert(agent_cert)

    if agent_urn:
        options['speaking_for'] = agent_urn

    try:
        agent_cert, revised_options = \
            determine_speaks_for(client_cert, credentials, options)
        agent_urn = get_urn_from_cert(agent_cert)
        client_urn = get_urn_from_cert(client_cert)
        if agent_cert == client_cert:
            print "Direct (not speaks-for): Agent = %s" % agent_urn
        else:
            print "Speaking for: Client = %s Agent = %s Options = %s" \
                % (client_urn, agent_urn, options)
    except Exception as e:
        print "Error: " + str(e)

                      