#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <err.h>
#include <fcntl.h>
#include <sys/stat.h>

#include <openssl/conf.h>
#include <openssl/ssl.h>
#include <openssl/evp.h>
#include <openssl/err.h>
#include <openssl/pem.h>
#include <openssl/x509.h>
#include <openssl/x509_vfy.h>
#include <openssl/x509v3.h>
#include <openssl/rsa.h>
#include <openssl/ocsp.h>

static int debug = 0;
static int verbose = 0;

#define PATH_CA_CERT "/usr/local/share/certs/ca-root-nss.crt"

typedef struct {
	char            *url;
	X509            *cert;
	X509            *issuer;
	X509_STORE	*store;
	X509            *sign_cert;
	EVP_PKEY        *sign_key;
	long            skew;
	long            maxage;
} spc_ocsprequest_t;

typedef enum {
	SPC_OCSPRESULT_ERROR_INVALIDRESPONSE   = -12,
	SPC_OCSPRESULT_ERROR_CONNECTFAILURE    = -11,
	SPC_OCSPRESULT_ERROR_SIGNFAILURE       = -10,
	SPC_OCSPRESULT_ERROR_BADOCSPADDRESS    = -9,
	SPC_OCSPRESULT_ERROR_OUTOFMEMORY       = -8,
	SPC_OCSPRESULT_ERROR_UNKNOWN           = -7,
	SPC_OCSPRESULT_ERROR_UNAUTHORIZED      = -6,
	SPC_OCSPRESULT_ERROR_SIGREQUIRED       = -5,
	SPC_OCSPRESULT_ERROR_TRYLATER          = -3,
	SPC_OCSPRESULT_ERROR_INTERNALERROR     = -2,
	SPC_OCSPRESULT_ERROR_MALFORMEDREQUEST  = -1,
	SPC_OCSPRESULT_CERTIFICATE_VALID       = 0,
  SPC_OCSPRESULT_CERTIFICATE_REVOKED     = 1
} spc_ocspresult_t;
 
// Is this failure worth crying over?
static int
spc_fatal_error(spc_ocspresult_t err)
{
	switch (err) {
	case SPC_OCSPRESULT_CERTIFICATE_VALID:
	case SPC_OCSPRESULT_ERROR_CONNECTFAILURE:
	case SPC_OCSPRESULT_ERROR_INVALIDRESPONSE:
	case SPC_OCSPRESULT_ERROR_BADOCSPADDRESS:
	case SPC_OCSPRESULT_ERROR_UNAUTHORIZED:
	case SPC_OCSPRESULT_ERROR_TRYLATER:
	case SPC_OCSPRESULT_ERROR_INTERNALERROR:
	case SPC_OCSPRESULT_ERROR_MALFORMEDREQUEST:
		return 0;
	case SPC_OCSPRESULT_ERROR_SIGNFAILURE:
	case SPC_OCSPRESULT_ERROR_OUTOFMEMORY:
	case SPC_OCSPRESULT_ERROR_UNKNOWN:
	case SPC_OCSPRESULT_ERROR_SIGREQUIRED:
	case SPC_OCSPRESULT_CERTIFICATE_REVOKED:
		return 1;
	}
}

//Calculates the length of a decoded base64 string
static int
calcDecodeLength(const char* b64input)
{
	int len = strlen(b64input);
	int padding = 0;
 
	if (b64input[len-1] == '=' && b64input[len-2] == '=') //last two chars are =
		padding = 2;
	else if (b64input[len-1] == '=') //last char is =
		padding = 1;
 
	return (int)len*0.75 - padding;
}

//Decodes a base64 encoded string
static int
Base64Decode(const char* b64message, char** buffer, size_t *bufferlenp)
{
	BIO *bio, *b64;
	int decodeLen = calcDecodeLength(b64message),
		len = 0;
	*buffer = (char*)malloc(decodeLen+1);
	FILE* stream = fmemopen((char*)b64message, strlen(b64message), "r");
 
	b64 = BIO_new(BIO_f_base64());
	bio = BIO_new_fp(stream, BIO_NOCLOSE);
	bio = BIO_push(b64, bio);
	BIO_set_flags(bio, BIO_FLAGS_BASE64_NO_NL); //Do not use newlines to flush buffer
	len = BIO_read(bio, *buffer, strlen(b64message));
	//Can test here if len == decodeLen - if not, then return an error
	(*buffer)[len] = '\0';
	if (bufferlenp)
		*bufferlenp = len;

	BIO_free_all(bio);
	fclose(stream);
 
	return (0); //success
}

static EVP_PKEY *
PublicKey(X509 *x509_certificate)
{
	EVP_PKEY *pkey = NULL;
	pkey = X509_get_pubkey(x509_certificate);
	if (pkey == NULL) {
		errx(1, "Unable to extract public key from x509 certificate");
	}
	return pkey;
}

/*
 * Load an x509 certificate from a fie.
 * This may be a CA file.
 */
static X509 *
LoadCertificate(const char *file)
{
	BIO *certbio = NULL;
	X509 *cert = NULL;
	int ret;

	certbio = BIO_new(BIO_s_file());
	if (certbio == NULL) {
		errx(1, "%s:  Could create BIO", __FUNCTION__);
	}
	BIO_read_filename(certbio, file);
	cert = PEM_read_bio_X509(certbio, NULL, 0, NULL);
	if (cert == NULL) {
		warnx("%s:  Could not read certificate from %s", __FUNCTION__, file);
	}
	BIO_free_all(certbio);
	if (verbose)
		warnx("%s(%s):  %s", __FUNCTION__, file, cert ? "Success" : "Failure");

	return cert;
}

static int
spc_verify_cert_hostname(X509 *cert, char *hostname) {
	int                   extcount, i, j, ok = 0;
	char                  name[256];
	X509_NAME             *subj;
	const char            *extstr;
	CONF_VALUE            *nval;
	unsigned char         *data;
	X509_EXTENSION        *ext;
	X509V3_EXT_METHOD     *meth;
	STACK_OF(CONF_VALUE)  *val;
   
	if ((extcount = X509_get_ext_count(cert)) > 0) {
		for (i = 0;  !ok && i < extcount;  i++) {
			ext = X509_get_ext(cert, i);
			extstr = OBJ_nid2sn(OBJ_obj2nid(X509_EXTENSION_get_object(ext)));
			if (!strcasecmp(extstr, "subjectAltName")) {
				if (!(meth = X509V3_EXT_get(ext))) break;
				data = ext->value->data;
   
				val = meth->i2v(meth, meth->d2i(0, (void*)&data, ext->value->length), 0);
				for (j = 0;  j < sk_CONF_VALUE_num(val);  j++) {
					nval = sk_CONF_VALUE_value(val, j);
					if (!strcasecmp(nval->name, "DNS") && !strcasecmp(nval->value, hostname)) {
						ok = 1;
						break;
					}
				}
			}
		}
	}
   
	if (!ok && (subj = X509_get_subject_name(cert)) &&
	    X509_NAME_get_text_by_NID(subj, NID_commonName, name, sizeof(name)) > 0) {
		name[sizeof(name) - 1] = '\0';
		if (!strcasecmp(name, hostname)) ok = 1;
	}
   
	return ok;
}

static BIO *
spc_connect_ssl(char *host,
		int port,
		X509_STORE *store,
		SSL_CTX **ctx)
{
	BIO *conn = 0;
	int our_ctx = 0;
	
	if (*ctx) {
		CRYPTO_add(&((*ctx)->references), 1, CRYPTO_LOCK_SSL_CTX);
		if (store && store != SSL_CTX_get_app_data(*ctx)) {
			SSL_CTX_set_cert_store(*ctx, store);
			SSL_CTX_set_app_data(*ctx, store);
		}
	} else {
		*ctx = (void*)store;
		our_ctx = 1;
	}
   
	if (!(conn = BIO_new_ssl_connect(*ctx))) goto error_exit;
	BIO_set_conn_hostname(conn, host);
	BIO_set_conn_int_port(conn, &port);
   
	if (BIO_do_connect(conn) <= 0) goto error_exit;
	if (our_ctx) SSL_CTX_free(*ctx);
	return conn;
   
error_exit:
	if (conn) BIO_free_all(conn);
	if (*ctx) SSL_CTX_free(*ctx);
	if (our_ctx) *ctx = 0;
	return 0;
}

static BIO *
spc_connect(char *host,
	    int port,
	    int ssl,
	    X509_STORE *store,
	    SSL_CTX **ctx)
{
	BIO *conn;
	SSL *ssl_ptr;
	
	if (ssl) {
		if (!(conn = spc_connect_ssl(host, port, store, ctx))) goto error_exit;
		BIO_get_ssl(conn, &ssl_ptr);
		if (!spc_verify_cert_hostname(SSL_get_peer_certificate(ssl_ptr), host))
			goto error_exit;
		if (SSL_get_verify_result(ssl_ptr) != X509_V_OK) goto error_exit;
		return conn;
	}
   
	*ctx = 0;
	if (!(conn = BIO_new_connect(host))) goto error_exit;
	BIO_set_conn_int_port(conn, &port);
	if (BIO_do_connect(conn) <= 0) goto error_exit;
	return conn;
   
error_exit:
	if (conn) BIO_free_all(conn);
	return 0;
}

static spc_ocspresult_t
spc_verify_via_ocsp(spc_ocsprequest_t *data) {
	BIO                   *bio = 0;
	int                   rc, reason, ssl, status;
	char                  *host = 0, *path = 0, *port = 0;
	SSL_CTX               *ctx = 0;
	X509_STORE            *store = 0;
	OCSP_CERTID           *id;
	OCSP_REQUEST          *req = 0;
	OCSP_RESPONSE         *resp = 0;
	OCSP_BASICRESP        *basic = 0;
	spc_ocspresult_t      result;
	ASN1_GENERALIZEDTIME  *producedAt, *thisUpdate, *nextUpdate;
   
	result = SPC_OCSPRESULT_ERROR_UNKNOWN;
	if (!OCSP_parse_url(data->url, &host, &port, &path, &ssl)) {
		result = SPC_OCSPRESULT_ERROR_BADOCSPADDRESS;
		goto end;
	}
	if (!(req = OCSP_REQUEST_new(  ))) {
		result = SPC_OCSPRESULT_ERROR_OUTOFMEMORY;
		goto end;
	}
   
	id = OCSP_cert_to_id(0, data->cert, data->issuer);
	if (!id || !OCSP_request_add0_id(req, id)) goto end;
	OCSP_request_add1_nonce(req, 0, -1);
   
	/* sign the request */
	if (data->sign_cert && data->sign_key &&
	    !OCSP_request_sign(req, data->sign_cert, data->sign_key, EVP_sha1(  ), 0, 0)) {
		result = SPC_OCSPRESULT_ERROR_SIGNFAILURE;
		goto end;
	}
   
	/* establish a connection to the OCSP responder */
	if (!(bio = spc_connect(host, atoi(port), ssl, data->store, &ctx))) {
		result = SPC_OCSPRESULT_ERROR_CONNECTFAILURE;
		goto end;
	}
   
	/* send the request and get a response */
	resp = OCSP_sendreq_bio(bio, path, req);
	if ((rc = OCSP_response_status(resp)) != OCSP_RESPONSE_STATUS_SUCCESSFUL) {
		switch (rc) {
		case OCSP_RESPONSE_STATUS_MALFORMEDREQUEST:
			result = SPC_OCSPRESULT_ERROR_MALFORMEDREQUEST; break;
		case OCSP_RESPONSE_STATUS_INTERNALERROR:
			result = SPC_OCSPRESULT_ERROR_INTERNALERROR;    break;
		case OCSP_RESPONSE_STATUS_TRYLATER:
			result = SPC_OCSPRESULT_ERROR_TRYLATER;         break;
		case OCSP_RESPONSE_STATUS_SIGREQUIRED:
			result = SPC_OCSPRESULT_ERROR_SIGREQUIRED;      break;
		case OCSP_RESPONSE_STATUS_UNAUTHORIZED:
			result = SPC_OCSPRESULT_ERROR_UNAUTHORIZED;     break;
		}
		goto end;
	}
  
	/* verify the response */
	result = SPC_OCSPRESULT_ERROR_INVALIDRESPONSE;
	if (!(basic = OCSP_response_get1_basic(resp))) goto end;
	if (OCSP_check_nonce(req, basic) <= 0) goto end;
	if ((rc = OCSP_basic_verify(basic, 0, data->store, 0)) <= 0) goto end;
   
	if (!OCSP_resp_find_status(basic, id, &status, &reason, &producedAt,
				   &thisUpdate, &nextUpdate))
		goto end;
	if (!OCSP_check_validity(thisUpdate, nextUpdate, data->skew, data->maxage))
		goto end;
  
	/* All done.  Set the return code based on the status from the response. */
	if (status == V_OCSP_CERTSTATUS_REVOKED)
		result = SPC_OCSPRESULT_CERTIFICATE_REVOKED;
	else
		result = SPC_OCSPRESULT_CERTIFICATE_VALID;
  
end:
	if (bio) BIO_free_all(bio);
	if (host) OPENSSL_free(host);
	if (port) OPENSSL_free(port);
	if (path) OPENSSL_free(path);
	if (req) OCSP_REQUEST_free(req);
	if (resp) OCSP_RESPONSE_free(resp);
	if (basic) OCSP_BASICRESP_free(basic);
	if (ctx) SSL_CTX_free(ctx);
	if (store) X509_STORE_free(store);
	return result;
}

/*
 * For OCSP, see
 * http://etutorials.org/Programming/secure+programming/Chapter+10.+Public+Key+Infrastructure/10.12+Checking+Revocation+Status+via+OCSP+with+OpenSSL/
 */
static int
VerifySignature(const char *data,
		const char *signature,
		const char *hash,
		spc_ocsprequest_t *ocsp)
{
	EVP_MD_CTX md_data = { 0 }, *ctx = &md_data;
	EVP_PKEY *pkey = NULL;
	int retval = 0;
	EVP_MD_CTX_init(ctx);
	const EVP_MD *digest = EVP_get_digestbyname(hash);
	char *decoded_signature = NULL;
	size_t decoded_length;

	/*
	 * First step:  if we've got a url and issuer, let's check
	 * and see if the key has been revoked.
	 */
	if (ocsp->url) {
		if (ocsp->issuer) {
			int rv = spc_verify_via_ocsp(ocsp);
			if (verbose) {
				if (rv)
					warnx("OSPC verify returned %d", rv);
				else
					warnx("Certificate valid");
			}
			if (spc_fatal_error(rv)) {
				errx(1, "Certificate check failed");
			}
		} else if (verbose)
			warnx("No issuer, cannot check OCSP");
	} else if (verbose)
		warnx("No OCSP URL, cannot check OCSP");

	pkey = PublicKey(ocsp->cert);

	if (digest == NULL) {
		errx(1, "Could not get hash algorigthm for '%s'", hash);
	}

	(void)Base64Decode(signature, &decoded_signature, &decoded_length);
	EVP_VerifyInit(ctx, digest);
	EVP_VerifyUpdate(ctx, data, strlen(data));

	retval = EVP_VerifyFinal(ctx, decoded_signature, decoded_length, pkey);
done:
	if (decoded_signature)
		free(decoded_signature);
	EVP_MD_CTX_cleanup(ctx);
	return retval;
}

static X509_STORE *
CreateStore(void)
{
	X509_STORE *retval = NULL;

	retval = X509_STORE_new();
	return retval;
}

static void
usage(void)
{
	errx(1, "Usge: -K certificate_file [-C ca_file] [-H hashtype] -S signature <-D data_file> | <data>");
}

int
main(int ac, char **av)
{
	spc_ocsprequest_t ocsp = { 0 };
	char *cert_file = NULL;
	char *ca_file = NULL;	// optional
	char *issuer_file = NULL;	// optional
	char *hash_type = "sha256";
	X509 *certificate = NULL;
	char *signature = NULL;
	char *data_file = NULL;
	char *data = NULL;
	EVP_PKEY *public_key = NULL;
	int opt;
	int retval;

	while ((opt = getopt(ac, av, "K:C:H:I:S:dv")) != -1) {
		switch (opt) {
		case 'K':	cert_file = strdup(optarg); break;
		case 'C':	ca_file = strdup(optarg); break;
		case 'H':	hash_type = strdup(optarg); break;
		case 'I':	issuer_file = strdup(optarg); break;
		case 'S':	signature = strdup(optarg); break;
		case 'D':	data_file = strdup(optarg); break;
		case 'd':	debug++; break;
		case 'v':	verbose++; break;
		default:	usage();
		}
	}
	ac -= optind;
	av += optind;

	if (ac == 0 && data_file == NULL) {
		warnx("No data or data file given");
		usage();
	}
	if (ac > 1) {
		warnx("Too many arguments");
		usage();
	}
	if (ac == 1 && data_file != NULL) {
		warnx("Data file and data argument given; pick one");
		usage();
	}
	if (ac == 1) {
		data = av[0];
	} else {
		int fd;
		size_t size;
		struct stat sbuf;

		if ((fd = open(data_file, O_RDONLY)) == -1) {
			err(1, "Cannot open data file %s", data_file);
		}
		fstat(fd, &sbuf);
		data = malloc(sbuf.st_size);
		if (data == NULL) {
			err(1, "Cannot allocate %zd bytes for data from file %s", (size_t)sbuf.st_size, data_file);
		}
		if (read(fd, data, sbuf.st_size) != sbuf.st_size) {
			err(1, "Cannot read data into buffer");
		}
		close(fd);
	}
	// Initialize lib crypto stuff
	ERR_load_crypto_strings();
	OpenSSL_add_all_algorithms();
	OPENSSL_config(NULL);
	
	// Create an x509 store
	ocsp.store = CreateStore();
	if (ocsp.store == NULL) {
		errx(1, "Could not create X509 store");
	}
	// If a CA file is given, load that
	if (ca_file) {
		certificate = LoadCertificate(ca_file);
		if (certificate) {
			// Add it to the store
			X509_STORE_add_cert(ocsp.store, certificate);
			if (verbose)
				warnx("Added %s certificate to store", ca_file);
		} else {
			warnx("Unable to load CA file %s", ca_file);
		}
	}
	// Now try the system CA; we don't care if it fails
	if (certificate = LoadCertificate(PATH_CA_CERT)) {
		X509_STORE_add_cert(ocsp.store, certificate);
		if (verbose)
			warnx("Added system CA %s to store", PATH_CA_CERT);
	}
		
	// Now load the actual certificate file
	if ((ocsp.cert = LoadCertificate(cert_file)) == NULL) {
		errx(1, "Unable to load certificate file %s", cert_file);
	} else {
		STACK *ocsp_urls = NULL;
		ocsp_urls = X509_get1_ocsp(ocsp.cert);
		if (ocsp_urls) {
			switch (sk_num(ocsp_urls)) {
			case 1:
				ocsp.url = sk_value(ocsp_urls, 0);
				if (verbose)
					warnx("OCSP URL %s", ocsp.url);
				break;
			case 0:
				break;
			default:
				warnx("Too many OCSP URLs (%d), don't know what to do", sk_num(ocsp_urls));
			}
		} else {
			if (verbose)
				warnx("No OCSP URL");
		}
	}

	// If we've been given an issuer, we can try OCSP.
	if (issuer_file) {
		ocsp.issuer = LoadCertificate(issuer_file);
	}
	retval = VerifySignature(data, signature, hash_type, &ocsp);
	if (verbose)
		warnx("%s", retval ? "Verified" : "FAILURE");

	EVP_cleanup();
	ERR_free_strings();

	return (retval == 1);
}
