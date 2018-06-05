# Compliance Test LSD Client for LSD server test
## Information

### Files: 

  - **lsd_client.py** : Script file for test 
  
  - **json_schema_lsd.json** : For check validation of Status document

### Tools: 

  - **Python 3.5.2**(Python software Foundation, Interpreter)
  
  - **PyCharm 2016.2.2** (JetBrain, IDE)

### Dependency: 

  - **pytz**(MIT license), **jsonschema**(MIT license)

### Prerequisites: 

  - epub files with LSD links provided by target LCP server(The Server must provide also LSDs associated with epub files)
  
  

## Detail

This script is used for verifying if a LSD server is compliant with LSD v1.0 specification

  >Usage
    
     $ python lsd_client.py -i %interaction_name -d %device_id -n %device_name $epub_file_name
     
       %interaction_name : which is one of following ones
       
         - fetch : fetch LSD from the server whose address is specified in the $epub_file_name
         
         - fetch_license : fetch License Document from the server whose address is specified in the LSD linked in $epub_file_name
         
         - register : request 'register' interaction to the server whose address is specified in the $epub_file_name
         
         - renew : request 'renew' interaction to the server whose address is specified in the $epub_file_name
         
         - return : request 'return' interaction to the server whose address is specified in the $epub_file_name
         
       %device_id : device id
       
       %device_name : device name
       
       %epub_file_name : specific epub_file which is provided by server to test an LSD interaction
       

  
