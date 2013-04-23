<?xml version="1.0" encoding="UTF-8"?>
<!-- https://svn.jenkins-ci.org/trunk/hudson/dtkit/dtkit-format/dtkit-junit-model/src/main/resources/com/thalesgroup/dtkit/junit/model/xsd/junit-4.xsd -->
<!-- http://stackoverflow.com/questions/4922867/junit-xml-format-specification-that-hudson-supports -->
<!-- http://stackoverflow.com/questions/721963/xslt-counting-elements-with-a-given-value -->
<!-- http://www.w3schools.com/xsl/xsl_apply_templates.asp -->

<xsl:stylesheet version="1.0" 
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:fn="http://www.w3.org/2005/xpath-functions"> 

<xsl:include href="job-report.junit.xsl"/>

<xsl:template match="testplan">
    <testsuites>
        <xsl:attribute name="name">
            <xsl:value-of select="plan/name"/>
        </xsl:attribute>
        <xsl:apply-templates select="jobs/testsuite" />
    </testsuites>
</xsl:template>

</xsl:stylesheet> 
<!-- vim: sw=2 -->
